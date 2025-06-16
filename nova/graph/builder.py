# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from nova.graph.configuration import Configuration
from nova.graph.mstate import OverallState
from nova.graph.nodes import (
    coordinator_node,
    planner_node,
    reporter_node,
    researcher_node,
    supervisor_node,
)

logger = logging.getLogger(__name__)


# ⭐
def build_graph(is_memory: bool = False):
    """Build and return the agent workflow graph."""
    # use persistent memory to save conversation history
    # ❗ TODO: be compatible with SQLite / PostgreSQL

    # build state graph
    workflow = StateGraph(OverallState, config_schema=Configuration)
    workflow.add_edge(START, "coordinator")
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("reporter", reporter_node)

    if is_memory:
        memory = InMemorySaver()
        app = workflow.compile(name="le_agent", checkpointer=memory)
    else:
        app = workflow.compile(name="le_agent")

    logger.info(">>>>>> Agent Workflow built successfully <<<<<< ")

    return app


app = build_graph()
# logger.info(app.get_graph(xray=True).draw_mermaid_png())
