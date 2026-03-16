# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime

from nova.hooks import Super_Agent_Hook_Instance
from nova.model.super_agent import SuperContext, SuperState
from nova.node.factory import NodeFactory

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


def create_chat_node(node_name="chat"):

    @Super_Agent_Hook_Instance.node_with_hooks(node_name=node_name)
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        return await NodeFactory.create_node(node_name, state=state, runtime=runtime)

    return _node


# 编译图
def compile_chat_agent():
    _chat_node = create_chat_node("chat")

    # chat graph
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("chat", _chat_node)
    _agent.add_edge(START, "chat")

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
