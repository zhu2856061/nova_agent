# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

from typing import cast

from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache
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
from langchain_litellm import ChatLiteLLM

from nova import CONF

# 启用内存缓存
set_llm_cache(InMemoryCache())

# Cache for LLM instances
_llm_cache: dict[str, ChatLiteLLM] = {}


# 🤖
def get_llm_by_type(llm_type: str) -> ChatLiteLLM:
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]

    llm_conf = CONF["LLM"].get(llm_type)
    if not llm_conf:
        raise ValueError(f"Unknown LLM type: {llm_type}")
    if not isinstance(llm_conf, dict):
        raise ValueError(f"Invalid LLM Conf: {llm_type}")

    llm = ChatLiteLLM(**llm_conf)

    _llm_cache[llm_type] = llm
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
