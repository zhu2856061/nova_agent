# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova.llms import get_llm_by_type
from nova.model.agent import Context, Messages, State
from nova.utils import log_error_set_color, log_info_set_color

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


# 函数
async def chat(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "chat"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _model_name = runtime.context.model
        _messages = state.messages.value

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(_messages)
        log_info_set_color(_thread_id, _NODE_NAME, response)

        return Command(
            goto="__end__",
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


# researcher subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("chat", chat)
_agent.add_edge(START, "chat")

checkpointer = InMemorySaver()
chat_agent = _agent.compile(checkpointer=checkpointer)
