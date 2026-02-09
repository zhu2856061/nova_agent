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

from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance
from nova.model.agent import Context, State

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


# 函数
@Agent_Hooks_Instance.node_with_hooks(node_name="chat")
async def chat(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "chat"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _messages = state.messages.value

    # 4 大模型
    response = await LLMS_Provider_Instance.llm_wrap_hooks(
        _thread_id,
        _NODE_NAME,
        _messages,
        _model_name,
    )

    return Command(
        goto="__end__",
        update={
            "code": 0,
            "err_message": "ok",
            "data": {_NODE_NAME: response},
        },
    )


def compile_chat_agent():
    checkpointer = InMemorySaver()
    # chat graph
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node("chat", chat)
    _agent.add_edge(START, "chat")

    return _agent.compile(checkpointer=checkpointer)
