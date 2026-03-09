# -*- coding: utf-8 -*-
# @Time   : 2026/03/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
from typing import Literal, cast

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from nova import CONF
from nova.hooks import Super_Agent_Hook_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.super_agent import SuperContext, SuperState
from nova.tools.digital_human_manager import Digital_Human_Manager

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量
def ask_clarification(
    question: str,
    clarification_type: Literal[
        "missing_info",
        "ambiguous_requirement",
        "approach_choice",
        "risk_confirmation",
        "suggestion",
    ],
    context: str | None = None,
    options: list[str] | None = None,
) -> str:
    return f"Clarification:\n\nquestion: {question}\n\nclarification_type: {clarification_type}\n\nreason: {context}\n\noptions: {options}"


# ######################################################################################


# 创建数字人节点
def create_digital_human_node(node_name, tools=None, structured_output=None):

    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 核心：组装提示词

        # 当前messages
        _messages = state.get("messages")

        base_agent_system_prompt = Prompts_Provider_Instance.get_template(
            "super_nova", "base_agent"
        )

        ask_clarification_system_prompt = Prompts_Provider_Instance.get_template(
            "super_nova", "ask_clarification"
        )

        web_search_system_prompt = Prompts_Provider_Instance.get_template(
            "super_nova", "web_search"
        )

        critical_reminders_system_prompt = Prompts_Provider_Instance.get_template(
            "super_nova", "critical_reminders"
        )

        _system_instruction = [
            base_agent_system_prompt,
            ask_clarification_system_prompt,
            web_search_system_prompt,
            critical_reminders_system_prompt,
        ]

        _system_instruction = "\n\n".join(_system_instruction)
        return [
            SystemMessage(content=_system_instruction),
        ] + _messages

    async def _after_model_hooks(
        state: SuperState, runtime: Runtime[SuperContext], response: AIMessage
    ):

        if response.tool_calls[-1]["name"] == "ask_clarification":
            res = ask_clarification(**response.tool_calls[-1]["args"])  # type: ignore
            response.content = res

        # 去掉冗余信息
        response.additional_kwargs = {}
        response.response_metadata = {}

        return Command(
            update={"messages": [response], "data": {"result": response.content}},
        )

    @Super_Agent_Hook_Instance.node_with_hooks(node_name=node_name)
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})
        # 创建工作目录
        _work_dir = os.path.join(cast(str, _task_dir), _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 获取状态变量
        _code = state.get("code", 0)
        if _code != 0:
            return Command(goto="__end__")

        _messages = state.get("messages")
        if not _messages:
            return Command(
                goto="__end__",
                update={"code": -1, "messages": [AIMessage(content="No messages")]},
            )

        # 模型执行前
        response = await _before_model_hooks(state, runtime)

        # 模型执行中
        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id,
            node_name,
            response,
            _model_name,
            tools=tools,
            structured_output=structured_output,
            **_config,  # type: ignore
        )
        # 模型执行后
        return await _after_model_hooks(state, runtime, response)

    return _node


# 人类反馈节点
def create_human_feedback_node(node_name):

    @Super_Agent_Hook_Instance.node_with_hooks(node_name=node_name)
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})
        # 创建工作目录
        _work_dir = os.path.join(cast(str, _task_dir), _thread_id)

        os.makedirs(_work_dir, exist_ok=True)

        # 获取状态变量
        _code = state.get("code", 0)
        if _code != 0:
            return Command(goto="__end__", update={"code": _code})

        _messages = state.get("messages")
        if not _messages:
            return Command(
                goto="__end__",
                update={"code": -1, "messages": [AIMessage(content="No messages")]},
            )
        # 断点
        value = interrupt(
            {
                "message_id": _thread_id,
                "content": _messages[-1].content,  # type: ignore
            }
        )

        logger.info(f"[Human Feedback] {_thread_id} {value}")

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=value["human_in_loop"],
                    )
                ]
            },
        )

    return _node


# 创建路由[主节点 -> 工具 | 人类反馈 | END ]的表，条件边
def create_route_tools_edges():
    """创建路由逻辑, 主要是路由到工具还是结束"""

    # 4. 定义路由逻辑：判断是否需要调用工具
    def route_edges(state: SuperState, runtime: Runtime[SuperContext]):
        """
        路由规则：
        - 如果最后一条消息包含 tool_calls → 跳转到 tools 节点
        - 否则 → 结束流程
        """
        # 变量
        _thread_id = runtime.context.get("thread_id", "default")

        _code = state.get("code", 0)
        if _code != 0:
            return "__end__"

        _messages = state.get("messages")
        if not _messages:
            return "__end__"

        if not isinstance(_messages[-1], AIMessage):
            return "__end__"

        last_message = cast(AIMessage, _messages[-1])

        # 检查LLM是否生成了工具调用指令
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
            )
            if last_message.tool_calls[-1]["name"] == "ask_clarification":
                return "human_feedback_node"
            return "tools"

        return "__end__"

    return route_edges


# ######################################################################################
# 编译图
def compile_super_nova_agent():

    # 节点和边
    tools = Digital_Human_Manager.copy()
    tools = [tools["ask_clarification"], tools["web_search"]]

    digital_human_node = create_digital_human_node(
        node_name="digital_human_node", tools=tools
    )
    human_feedback_node = create_human_feedback_node(node_name="human_feedback_node")
    tool_node = ToolNode(tools=tools)
    route_edges = create_route_tools_edges()

    # 构建图
    _agent = StateGraph(SuperState, context_schema=SuperContext)
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
