# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import os
from typing import cast

from langchain.globals import set_llm_cache
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

from core import CONF
from core.llms.fix_llm_cache import SQLiteCacheFixed

# ######################################################################################
# 配置
LLM_CONFIG = CONF["LLM"]
SYSTEM_CONFIG = CONF["SYSTEM"]

# ######################################################################################
# 全局变量


# ######################################################################################
# 本地变量
_llm_instance_cache: dict[str, ChatLiteLLM] = {}
_litellm_router = Router(model_list=LLM_CONFIG)


# ######################################################################################
# 其他
# 设置 SQLite 缓存，指定数据库文件名
os.makedirs(SYSTEM_CONFIG["cache_dir"], exist_ok=True)
set_llm_cache(
    SQLiteCacheFixed(
        database_path=os.path.join(SYSTEM_CONFIG["cache_dir"], "llm_cache.db")
    )
)


# ######################################################################################
# 函数
def get_llm_by_type(llm_type: str):
    if llm_type in _llm_instance_cache:
        return _llm_instance_cache[llm_type]
    llm = ChatLiteLLMRouter(router=_litellm_router, model_name=llm_type)
    _llm_instance_cache[llm_type] = llm
    return llm


def with_structured_output(llm, schema):
    if type(llm).bind_tools is BaseChatModel.bind_tools:
        msg = "with_structured_output is not implemented for this model."
        raise NotImplementedError(msg)

    llm = llm.bind_tools(
        [schema],
        tool_choice="auto",
        ls_structured_output_format={
            "kwargs": {"method": "function_calling"},
            "schema": schema,
        },
    )
    if isinstance(schema, type) and is_basemodel_subclass(schema):
        output_parser: OutputParserLike = PydanticToolsParser(
            tools=[cast("TypeBaseModel", schema)],  # type: ignore
            first_tool_only=True,
        )
    else:
        key_name = convert_to_openai_tool(schema)["function"]["name"]
        output_parser = JsonOutputKeyToolsParser(
            key_name=key_name, first_tool_only=True
        )

    return llm | output_parser
