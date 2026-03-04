# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from nova.model.agent import Context, State
from nova.node.common import create_route_tools_edges, create_tool_node
from nova.node.digital_human import create_digital_human_node
from nova.tools.digital_human_manager import Digital_Human_Manager

# from nova.node.factory import (
#     create_agent_with_todos_skills_tools_node,
#     create_patch_tools_node,
#     create_summarization_node,
# )
# from nova.tools import write_todos

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################

# 函数 - 采用通用节点创建方式

# patch_tools_node = create_patch_tools_node()
# summarization_node = create_summarization_node(10)
# agent_with_skills_tools_node, tools = create_agent_with_todos_skills_tools_node()
tools = list(Digital_Human_Manager.values())
agent = create_digital_human_node(node_name="digital_human_node", tools=tools)
tool_node = create_tool_node(tools=tools)
route_edges = create_route_tools_edges()


def compile_super_nova_agent():
    # chat graph
    _agent = StateGraph(State, context_schema=Context)

    _agent.add_node("step1", agent)
    _agent.add_node("tools", tool_node)
    _agent.add_edge(START, "step1")
    _agent.add_edge("tools", "step1")

    _agent.add_conditional_edges(
        source="step1",
        path=route_edges,
        path_map={
            "tools": "tools",  # 路由到 tools 节点
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
