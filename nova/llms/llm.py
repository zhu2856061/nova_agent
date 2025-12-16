# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Type, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers.base import OutputParserLike
from langchain_core.output_parsers.openai_tools import (
    JsonOutputKeyToolsParser,
    PydanticToolsParser,
)
from langchain_core.utils.function_calling import (
    convert_to_openai_tool,
)
from langchain_core.utils.pydantic import TypeBaseModel, is_basemodel_subclass
from langchain_litellm import ChatLiteLLM, ChatLiteLLMRouter
from litellm import Router  # type: ignore

from nova import CONF
from nova.memory import SQLITECACHE

# ######################################################################################
# 配置
LLM_CONFIG = CONF["LLM"]
SYSTEM_CONFIG = CONF["SYSTEM"]

# ######################################################################################
# 全局变量

# 缓存 LLM 实例，避免重复创建（key: 模型类型, value: ChatLiteLLM 实例）
_llm_instance_cache: dict[str, ChatLiteLLM] = {}

# ######################################################################################
# 本地变量

# 初始化 LiteLLM 路由实例：支持多模型路由、故障转移、负载均衡
# 配置来源：LLM_CONFIG 需包含 model_list 字段，格式参考 litellm.Router 要求
_litellm_router = Router(model_list=LLM_CONFIG)


# ######################################################################################
# 其他


# ######################################################################################
# 函数
def get_llm_by_type(llm_type: str):
    if llm_type in _llm_instance_cache:
        return _llm_instance_cache[llm_type]

    try:
        llm = ChatLiteLLMRouter(router=_litellm_router, model_name=llm_type)
        llm.cache = SQLITECACHE
        _llm_instance_cache[llm_type] = llm

    except Exception as e:
        raise ValueError(f"初始化 LLM 实例失败（类型：{llm_type}）: {str(e)}") from e

    return llm


def with_structured_output(
    llm: BaseChatModel,
    schema: Type[TypeBaseModel] | dict,
):
    """
    为 LLM 绑定结构化输出能力（基于 OpenAI 工具调用规范）

    Args:
        llm: 基础 LLM 实例（需支持 bind_tools 方法）
        schema: 输出结构定义（Pydantic 模型 或 OpenAI 工具格式的字典）

    Returns:
        链式调用对象：LLM + 结构化输出解析器

    Raises:
        NotImplementedError: 若 LLM 不支持 bind_tools 方法
        ValueError: 若 schema 格式不合法
    """
    # 1. 校验模型是否支持工具调用
    # 注意：BaseChatModel.bind_tools 是基类方法，需判断实例是否重写该方法
    if getattr(llm.__class__, "bind_tools") is BaseChatModel.bind_tools:
        raise NotImplementedError(
            f"模型 {llm.__class__.__name__} 未实现 bind_tools 方法，不支持结构化输出"
        )

    # if type(llm).bind_tools is BaseChatModel.bind_tools:
    #     msg = "with_structured_output is not implemented for this model."
    #     raise NotImplementedError(msg)
    try:
        # 2. 绑定工具调用规则（强制结构化输出）
        llm_with_tools = llm.bind_tools(
            tools=[schema],  # 输出结构定义
            tool_choice="auto",  # 自动选择工具（此处仅一个工具，等价于强制使用）
            # 结构化输出格式配置（LangChain 内部参数）
            ls_structured_output_format={
                "kwargs": {"method": "function_calling"},  # 基于函数调用实现结构化输出
                "schema": schema,
            },
        )
        # 3. 根据 schema 类型选择对应的解析器
        if isinstance(schema, type) and is_basemodel_subclass(schema):
            # 场景1：Pydantic 模型 → 使用 PydanticToolsParser 解析
            output_parser: OutputParserLike = PydanticToolsParser(
                tools=[cast(TypeBaseModel, schema)],
                first_tool_only=True,  # 仅解析第一个工具的输出（符合单结构场景）
            )
        else:
            # 场景2：字典格式 → 解析为 JSON 并提取指定字段
            try:
                tool_info = convert_to_openai_tool(schema)
                key_name = tool_info["function"]["name"]
            except KeyError as e:
                raise ValueError(
                    f"schema 格式不合法，缺少字段 {e}（需符合 OpenAI 工具格式）"
                ) from e

            output_parser = JsonOutputKeyToolsParser(
                key_name=key_name,
                first_tool_only=True,
            )

        # 4. 链式组合：LLM 调用 + 结构化输出解析
        return llm_with_tools | output_parser

    except Exception as e:
        raise ValueError(f"绑定结构化输出失败: {str(e)}") from e
