# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

from typing import Annotated

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from core.llms import get_llm_by_type
from core.prompts.template import apply_system_prompt_template
from core.tools import crawl_tool, serp_tool

# ######################################################################################
# 配置


# ######################################################################################
# 全局变量
class State(TypedDict):
    messages: Annotated[list, add_messages]


class Context(TypedDict):
    trace_id: str
    deep_search_model: str
    number_of_initial_queries: int
    max_research_loops: int


# ######################################################################################
# 函数
async def deepsearch(state: State, runtime: Runtime[Context]):
    # 变量
    _model_name = runtime.context.get("deep_search_model", "basic")

    def _assemble_prompt():
        """
        组装成提示 system message + user message
        SystemMessage + HumanMessage[question]
        """
        system_messages = apply_system_prompt_template("searcher", state)

        all_messages = [SystemMessage(system_messages)] + state["messages"]

        return all_messages

    async def _execute_llm(messages):
        """执行LLM"""
        response = await (
            get_llm_by_type(_model_name)
            .bind_tools([crawl_tool, serp_tool])
            .ainvoke(messages)
        )
        return response

    # 1 构建prompt
    messages = _assemble_prompt()

    # 2 执行LLM
    response = await _execute_llm(messages)

    return {"messages": [response]}


tool_node = ToolNode(tools=[crawl_tool, serp_tool])

graph_builder = StateGraph(State, context_schema=Context)
graph_builder.add_node("deepsearch", deepsearch)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges("deepsearch", tools_condition)
graph_builder.add_edge("tools", "deepsearch")

graph_builder.add_edge(START, "deepsearch")
graph_builder.add_edge("deepsearch", END)
graph = graph_builder.compile()
