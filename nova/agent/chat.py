# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from nova.model.super_agent import SuperContext, SuperState
from nova.node.common import create_node

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


# 编译图
def compile_chat_agent():
    _chat_node = create_node("chat")

    # chat graph
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("chat", _chat_node)
    _agent.add_edge(START, "chat")

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
