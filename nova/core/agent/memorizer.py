# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Annotated, Literal, cast

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command

from nova.core.llms import get_llm_by_type
from nova.core.memory import SQLITESTORE
from nova.core.prompts.menorizer import apply_system_prompt_template
from nova.core.tools import upsert_memory_tool
from nova.core.utils import (
    get_today_str,
    set_color,
)

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量
@dataclass(kw_only=True)
class MemoryState:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    memorizer_messages: Annotated[list[AnyMessage], add_messages]


@dataclass(kw_only=True)
class Context:
    trace_id: str = field(
        default="default",
        metadata={"description": "The trace_id to use for the agent."},
    )

    user_id: str = ""
    memorizer_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )


# ######################################################################################
# 函数
async def memorizer(
    state: MemoryState, runtime: Runtime[Context]
) -> Command[Literal["__end__", "memorizer_tools"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _user_id = runtime.context.user_id
        _model_name = runtime.context.memorizer_model
        _messages = state.memorizer_messages

        if _user_id == "":
            return Command(
                goto="__end__",
                update={
                    "memorizer_messages": ["[Error]: user_id is empty"],
                },
            )
        memories = await cast(BaseStore, runtime.store).asearch(
            ("memories", _user_id),
            query=str([m.content for m in _messages[-3:]]),
            limit=10,
        )

        logger.info(f"{_user_id} history: {memories}")

        # 提示词
        def _assemble_prompt(messages):
            # Retrieve the most recent memories for context

            # Format memories for inclusion in the prompt
            formatted = "\n".join(f"[{mem.key}]: {mem.value}" for mem in memories)

            messages = [
                SystemMessage(
                    content=apply_system_prompt_template(
                        "call_model_system",
                        {"user_info": formatted, "date": get_today_str()},
                    )
                )
            ] + messages

            return messages

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        _tmp_messages = _assemble_prompt(_messages)

        msg = await _get_llm().bind_tools([upsert_memory_tool]).ainvoke(_tmp_messages)

        goto = "__end__"
        if getattr(msg, "tool_calls", None):
            goto = "memorizer_tools"

        return Command(
            goto=goto,
            update={
                "memorizer_messages": [msg],
            },
        )

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=call_model | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=researcher_tools | error={e}"
            },
        )


async def execute_tool_safely(tool, args):
    try:
        return await tool._arun(**args)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def memorizer_tools(
    state: MemoryState, runtime: Runtime[Context]
) -> Command[Literal["memorizer"]]:
    _trace_id = runtime.context.trace_id
    _user_id = runtime.context.user_id

    # Extract tool calls from the last message
    tool_calls = getattr(state.memorizer_messages[-1], "tool_calls", [])
    # Concurrently execute all upsert_memory calls
    _upsert_memorys = []
    for tc in tool_calls:
        _upsert_memorys.append(
            execute_tool_safely(
                upsert_memory_tool,
                {
                    **tc["args"],
                    "trace_id": _trace_id,
                    "memory_id": None,
                    "user_id": _user_id,
                    "store": cast(BaseStore, runtime.store),
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
    return Command(goto="memorizer", update={"memorizer_messages": results})


# researcher subgraph
_agent = StateGraph(MemoryState, context_schema=Context)
_agent.add_node("memorizer", memorizer)
_agent.add_node("memorizer_tools", memorizer_tools)
_agent.add_edge(START, "memorizer")


memorizer_agent = _agent.compile(store=SQLITESTORE)
