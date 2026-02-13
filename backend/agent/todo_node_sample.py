# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from nova.model.agent import Context, State
from nova.node.factory import create_todos_list_node

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################

# 函数
todos_list_node = create_todos_list_node()


def compile_todos_list_agent():
    # chat graph
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node("todos_list", todos_list_node)
    _agent.add_edge(START, "todos_list")

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
