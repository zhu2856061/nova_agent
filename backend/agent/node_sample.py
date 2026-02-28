# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode

from nova.model.agent import Context, State
from nova.node.factory import (
    create_agent_with_todos_skills_tools_node,
    create_patch_tools_node,
    create_route_edges,
    create_summarization_node,
    create_todos_list_node,
    create_tool_node,
)

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################

# 函数
todos_list_node = create_todos_list_node()
patch_tools_node = create_patch_tools_node()
summarization_node = create_summarization_node(10)
agent_with_skills_tools_node, tools = create_agent_with_todos_skills_tools_node()
tool_node = create_tool_node(tools=tools)
route_edges = create_route_edges()


def compile_node_agent():
    # chat graph
    _agent = StateGraph(State, context_schema=Context)
    # _agent.add_node("step1", todos_list_node)
    # _agent.add_node("step2", patch_tools_node)
    # _agent.add_node("step3", summarization_node)
    _agent.add_node("step4", agent_with_skills_tools_node)
    _agent.add_node("tools", tool_node)

    _agent.add_edge(START, "step4")

    _agent.add_conditional_edges(
        source="step4",
        path=route_edges,
        path_map={
            "tools": "tools",  # 路由到 tools 节点
            "__end__": "__end__",  # 结束流程
        },
    )
    _agent.add_edge("tools", "step4")

    # _agent.add_edge("step1", "step2")
    # _agent.add_edge("step2", "step3")
    # _agent.add_edge("step3", "step4")

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
