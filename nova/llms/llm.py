# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import time
from typing import Any, Type, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
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
from pydantic import BaseModel

from nova import CONF
from nova.memory import SQLITECACHE
from nova.utils.log_utils import log_error_set_color, log_info_set_color

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


class LLMHooks:
    @staticmethod
    async def before_llm(
        thread_id: str,
        node_name: str,
        messages: list[BaseMessage],
    ):
        msg_count = len(messages)
        last_content = f"{messages[-1].content[:80]}..." if messages else ""
        message = f"[LLM Call] -> messages: {msg_count} | last: {last_content}"

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：prompt 注入、敏感词过滤、修改 messages、动态调整 temperature 等

    @staticmethod
    async def after_llm(
        thread_id: str,
        node_name: str,
        response: Any,
        elapsed: float,
    ):
        tool_calls = 0

        if isinstance(response, AIMessage):
            _result = response.content
            tool_calls = (
                len(response.tool_calls) if hasattr(response, "tool_calls") else 0
            )
        elif isinstance(response, BaseModel):
            _result = response.model_dump()
        else:
            _result = response
        _result = str(_result)

        content_preview = f"{_result[:80]}..." if _result else ""

        usage = getattr(response, "usage_metadata", None)
        tokens_str = (
            f" in:{usage.get('input_tokens', '?')} out:{usage.get('output_tokens', '?')}"
            if usage
            else ""
        )
        message = f"[LLM Returned: {elapsed:.3f}s] <- tools:{tool_calls} | tokens:{tokens_str} | response:{content_preview}"

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：输出校验、PII 脱敏、自动总结等

    @staticmethod
    async def on_error(thread_id: str, node_name: str, exc: Exception):
        _err_message = log_error_set_color(thread_id, node_name, exc)
        return _err_message
        # 可扩展：统一错误上报、转成 AIMessage 错误回复


# ─── LLM 调用包装器（实现 LLM 前 + LLM 后） ───
async def llm_with_hooks(
    thread_id: str,
    node_name: str,
    messages: list,
    model_name: str,
    *,
    tools: list | None = None,
    structured_output: Any = None,
    **invoke_kwargs,
):
    await LLMHooks.before_llm(thread_id, node_name, messages)

    start = time.perf_counter()
    try:
        if tools:
            model = get_llm_by_type(model_name).bind_tools(tools)
        elif structured_output:
            model = get_llm_by_type(model_name).with_structured_output(
                structured_output
            )
        else:
            model = get_llm_by_type(model_name)

        response: AIMessage = await model.ainvoke(messages, **invoke_kwargs)  # type: ignore

        elapsed = time.perf_counter() - start
        await LLMHooks.after_llm(thread_id, node_name, response, elapsed)

        # 可选：在这里记录总耗时、token 等
        return response

    except Exception as e:
        await LLMHooks.on_error(thread_id, node_name, e)
        raise  # 或返回错误 AIMessage


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
