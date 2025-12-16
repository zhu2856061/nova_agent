# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
from typing import cast

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command

from nova.llms import get_llm_by_type
from nova.memory import SQLITESTORE
from nova.model.agent import Context, Messages, State
from nova.prompts.template import apply_prompt_template, get_prompt
from nova.tools.memory_manager import upsert_memory_tool
from nova.utils.common import get_today_str
from nova.utils.log_utils import log_error_set_color, log_info_set_color

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


# 函数
async def memorizer(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "memorizer"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _model_name = runtime.context.model
        _config = runtime.context.config
        _messages = state.messages.value

        if _config.get("user_id") is None or len(_messages) <= 0:
            _err_message = log_error_set_color(
                _thread_id, _NODE_NAME, "user_id is empty"
            )
            return Command(
                goto="__end__", update={"code": 1, "err_message": _err_message}
            )

        _user_id = cast(str, _config.get("user_id"))

        # 提示词
        async def _assemble_prompt(messages):
            # Retrieve the most recent memories for context
            memories = await cast(BaseStore, SQLITESTORE).asearch(
                ("memories", _user_id),
                query=str([m.content for m in _messages[-3:]]),  # type: ignore
                limit=10,
            )

            # Format memories for inclusion in the prompt
            tmp = {
                "user_info": "\n".join(f"[{mem.key}]: {mem.value}" for mem in memories),
                "date": get_today_str(),
            }

            _prompt_tamplate = get_prompt("memorizer", _NODE_NAME)
            return [
                SystemMessage(content=apply_prompt_template(_prompt_tamplate, tmp))
            ] + messages

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).bind_tools([upsert_memory_tool])

        response = await _get_llm().ainvoke(await _assemble_prompt(_messages))
        log_info_set_color(_thread_id, _NODE_NAME, response)

        # 判断是否有工具调用
        tool_calls = getattr(response, "tool_calls", [])

        if not tool_calls:  # 如果没有工具调用，则正常返回 - 回复结果
            return Command(
                goto="__end__",
                update={
                    "code": 0,
                    "err_message": "ok",
                    "data": {_NODE_NAME: response},
                },
            )

        return Command(
            goto="memorizer_tools",
            update={
                "code": 0,
                "err_message": "ok",
                "data": {_NODE_NAME: response},
            },
        )

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": _err_message,
                "messages": Messages(type="end"),
            },
        )


async def execute_tool_safely(tool, args):
    try:
        return await tool._arun(**args)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def memorizer_tools(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "memorizer_tools"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _config = runtime.context.config
        _data = state.data

        if _config.get("user_id") is None or _data is None:
            _err_message = log_error_set_color(
                _thread_id, _NODE_NAME, "user_id is empty"
            )
            return Command(
                goto="__end__",
                update={
                    "code": 1,
                    "err_message": _err_message,
                    "messages": Messages(type="end"),
                },
            )

        _user_id = cast(str, _config.get("user_id"))

        # Extract tool calls from the last message
        tool_calls = getattr(_data.get("memorizer"), "tool_calls", [])
        if not tool_calls:
            _err_message = log_error_set_color(
                _thread_id, _NODE_NAME, "no tool calls found"
            )
            return Command(
                goto="__end__",
                update={
                    "code": 1,
                    "err_message": _err_message,
                    "messages": Messages(type="end"),
                },
            )

        # Concurrently execute all upsert_memory calls
        _upsert_memorys = []
        for tc in tool_calls:
            _upsert_memorys.append(
                execute_tool_safely(
                    upsert_memory_tool,
                    {
                        **tc["args"],
                        "trace_id": _thread_id,
                        "memory_id": None,
                        "user_id": _user_id,
                    },
                )
            )

        saved_memories = await asyncio.gather(*_upsert_memorys)
        # Format the results of memory storage operations
        # This provides confirmation to the model that the actions it took were completed
        results = [
            {
                "role": "tool",
                "content": mem,
                "tool_call_id": tc["id"],
            }
            for tc, mem in zip(tool_calls, saved_memories)
        ]

        log_info_set_color(_thread_id, _NODE_NAME, results)
        return Command(
            goto="__end__",
            update={
                "code": 0,
                "err_message": "ok",
                "data": {_NODE_NAME: results},
            },
        )

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return Command(goto="__end__", update={"code": 1, "err_message": _err_message})


# researcher subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("memorizer", memorizer)
_agent.add_node("memorizer_tools", memorizer_tools)

_agent.add_edge(START, "memorizer")

checkpointer = InMemorySaver()
memorizer_agent = _agent.compile(checkpointer=checkpointer)
