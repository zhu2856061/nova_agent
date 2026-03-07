# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from nova.model.agent import Context, State
from nova.node.common import create_tool_node
from nova.node.digital_human import (
    create_digital_human_node,
    create_human_feedback_node,
    create_route_tools_edges,
)
from nova.tools.digital_human_manager import Digital_Human_Manager

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
digital_human_node = create_digital_human_node(
    node_name="digital_human_node", tools=tools
)
human_feedback_node = create_human_feedback_node(node_name="human_feedback_node")
tool_node = create_tool_node(tools=tools)

route_edges = create_route_tools_edges()


def compile_super_nova_agent():
    # chat graph
    _agent = StateGraph(State, context_schema=Context)

    _agent.add_node("digital_human_node", digital_human_node)
    _agent.add_node("human_feedback_node", human_feedback_node)
    _agent.add_node("tools", tool_node)
    _agent.add_edge(START, "digital_human_node")
    _agent.add_edge("tools", "digital_human_node")
    _agent.add_edge("human_feedback_node", "digital_human_node")

    _agent.add_conditional_edges(
        source="digital_human_node",
        path=route_edges,
        path_map={
            "tools": "tools",  # 路由到 tools 节点
            "human_feedback_node": "human_feedback_node",
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
