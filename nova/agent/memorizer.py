# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Literal, Optional, cast

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command

from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.memory import SQLITESTORE
from nova.model.agent import Context, Messages, State
from nova.tools import upsert_memory_tool
from nova.utils.common import extract_ai_message_content, get_today_str
from nova.utils.log_utils import log_error_set_color

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################
# 函数


async def upsert_memory(
    content: str,
    context: str,
    *,
    # Hide these arguments from the model.
    user_id: str,
    store: BaseStore,
    memory_id: Optional[str] = None,
):
    """Upsert a memory in the database.

    If a memory conflicts with an existing one, then just UPDATE the
    existing one by passing in memory_id - don't create two memories
    that are the same. If the user corrects a memory, UPDATE it.

    Args:
        content: The main content of the memory. For example:
            "User expressed interest in learning about French."
        context: Additional context for the memory. For example:
            "This was mentioned while discussing career options in Europe."
        memory_id: ONLY PROVIDE IF UPDATING AN EXISTING MEMORY.
        The memory to overwrite.
    """

    mem_id = memory_id or uuid.uuid4()
    await store.aput(
        ("memories", user_id),
        key=str(mem_id),
        value={"content": content, "context": context},
    )

    return f"Stored memory {mem_id}"


# 函数
@Agent_Hooks_Instance.node_with_hooks(node_name="memorizer")
async def memorizer(
    state: State, runtime: Runtime[Context], **kwargs
) -> Command[Literal["memorizer_tools", "__end__"]]:
    _NODE_NAME = "memorizer"

    # 1 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _config = runtime.context.config
    _messages = (
        state.messages.value if isinstance(state.messages, Messages) else state.messages
    )

    # 2 变量检查
    if _config.get("user_id") is None or len(_messages) <= 0:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, "user_id is empty")
        return Command(goto="__end__", update={"code": 1, "err_message": _err_message})

    _user_id = cast(str, _config.get("user_id"))

    # 3 提示词
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

        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "memorizer", _NODE_NAME
        )
        return [
            SystemMessage(
                content=Prompts_Provider_Instance.prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ] + messages

        # LLM

    # 4 大模型
    response = await LLMS_Provider_Instance.llm_wrap_hooks(
        _thread_id,
        _NODE_NAME,
        await _assemble_prompt(_messages),
        _model_name,
        tools=[upsert_memory_tool],
    )

    # 5 判断下一个节点的逻辑
    tool_calls = getattr(response, "tool_calls", [])
    if not tool_calls:  # 如果没有工具调用，则正常返回 - 回复结果
        content, reasoning_content = extract_ai_message_content(response)
        return Command(
            goto="__end__",
            update={
                "code": 0,
                "err_message": "ok",
                "data": {"content": content, "reasoning_content": reasoning_content},
            },
        )

    return Command(
        goto="memorizer_tools",
        update={
            "code": 0,
            "err_message": "ok",
            "data": {"result": response},
        },
    )


@Agent_Hooks_Instance.node_with_hooks(node_name="memorizer_tools")
async def memorizer_tools(
    state: State, runtime: Runtime[Context], **kwargs
) -> Command[Literal["__end__"]]:
    _NODE_NAME = "memorizer_tools"

    # 变量
    _thread_id = runtime.context.thread_id
    _config = runtime.context.config
    _data = state.data

    if _config.get("user_id") is None or _data is None:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, "user_id is empty")
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
    tool_calls = getattr(_data.get("result"), "tool_calls", [])
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
        content = tc["args"].get("content")
        context = tc["args"].get("context")
        if not content or not context:
            continue
        _upsert_memorys.append(
            upsert_memory(
                content=content, context=context, user_id=_user_id, store=SQLITESTORE
            ),
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

    return Command(
        goto="__end__",
        update={
            "code": 0,
            "err_message": "ok",
            "data": {"result": results},
        },
    )


def compile_memorizer_agent():
    # researcher subgraph
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node("memorizer", memorizer)
    _agent.add_node("memorizer_tools", memorizer_tools)
    _agent.add_edge(START, "memorizer")

    checkpointer = InMemorySaver()

    return _agent.compile(checkpointer=checkpointer)
