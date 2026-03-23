# -*- coding: utf-8 -*-
# @Time   : 2026/03/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
from typing import cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import ToolCall
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from nova import CONF
from nova.model.super_agent import SuperContext, SuperState
from nova.provider import (
    get_llms_provider,
    get_prompts_provider,
    get_skill_provider,
    get_super_agent_hooks,
)
from nova.tools import Digital_Human_Manager
from nova.tools.ask_clarification import format_clarification_message
from nova.utils.common import get_today_str

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


def _handle_clarification(request: ToolCall) -> ToolMessage:
    """Handle clarification request and return command to interrupt execution.

    Args:
        request: Tool call request

    Returns:
        Command that interrupts execution with the formatted clarification message
    """
    # Extract clarification arguments
    args = request["args"]

    question = args.get("question", "")

    logger.info("[ClarificationMiddleware] Intercepted clarification request")
    logger.info(f"[ClarificationMiddleware] Question: {question}")

    # Format the clarification message
    formatted_message = format_clarification_message(args)

    # Get the tool call ID
    tool_call_id = request.get("id", "")

    # Create a ToolMessage with the formatted question
    # This will be added to the message history
    tool_message = ToolMessage(
        content=formatted_message,
        tool_call_id=tool_call_id,
        name="ask_clarification",
    )

    # Return a Command that:
    # 1. Adds the formatted tool message
    # 2. Interrupts execution by going to __end__
    # Note: We don't add an extra AIMessage here - the frontend will detect
    # and display ask_clarification tool messages directly
    return tool_message


# ######################################################################################


# 创建数字人节点
def create_super_nova_node(node_name="super_nova", tools=None, structured_output=None):
    _hook = get_super_agent_hooks()

    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 核心：组装提示词

        # 基础提示
        base_agent_system_prompt = get_prompts_provider().prompt_apply_template(
            get_prompts_provider().get_template("super_nova", "base_agent"),
            {"date": get_today_str()},
        )

        # 加入澄清
        ask_clarification_system_prompt = get_prompts_provider().get_template(
            "tools", "ask_clarification"
        )

        # 加入todo list
        todo_list_system_prompt = get_prompts_provider().get_template(
            "tools", "write_todos"
        )

        # 加入网络搜索
        web_search_system_prompt = get_prompts_provider().get_template(
            "tools", "web_search"
        )

        # 加入文件操作
        _thread_id = runtime.context.get("thread_id", "default")
        _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
        _work_dir = os.path.join(cast(str, _task_dir), _thread_id)

        filesystem_system_prompt = get_prompts_provider().prompt_apply_template(
            get_prompts_provider().get_template("tools", "filesystem"),
            {"work_dir": _work_dir},
        )

        # 加入代码执行
        execute_tool_system_prompt = get_prompts_provider().get_template(
            "super_nova", "execute_tool"
        )

        # 加入Skills
        skill_system_prompt = get_skill_provider().get_skill_prompt_template()

        # 重要提醒
        critical_reminders_system_prompt = get_prompts_provider().prompt_apply_template(
            get_prompts_provider().get_template("super_nova", "critical_reminders"),
            {"work_dir": _work_dir},
        )

        _system_instruction = [
            base_agent_system_prompt,
            ask_clarification_system_prompt,
            todo_list_system_prompt,
            web_search_system_prompt,
            filesystem_system_prompt,
            execute_tool_system_prompt,
            skill_system_prompt,
            critical_reminders_system_prompt,
        ]

        # 当前messages
        _messages = cast(list[AnyMessage], state.get("messages"))

        _system_instruction = "\n\n".join(_system_instruction)
        return [
            SystemMessage(content=_system_instruction),
        ] + _messages

    async def _after_model_hooks(
        state: SuperState, runtime: Runtime[SuperContext], response: AIMessage
    ):

        tmp = response
        if (
            response.tool_calls
            and response.tool_calls[-1]["name"] == "ask_clarification"
        ):
            # res = ask_clarification(**response.tool_calls[-1]["args"])  # type: ignore
            # response.content = res

            tmp = _handle_clarification(response.tool_calls[-1])

        # 去掉冗余信息
        tmp.additional_kwargs = {}
        tmp.response_metadata = {}

        return Command(
            update={
                "messages": [tmp],
                "data": {"result": tmp.content},
            },
        )

    @_hook.node_with_hooks(node_name=node_name)
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
                update={"code": -1, "err_message": "No messages"},
            )

        # 模型执行前
        response = await _before_model_hooks(state, runtime)

        # 模型执行中
        response = await get_llms_provider().llm_wrap_hooks(
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
    _hook = get_super_agent_hooks()

    @_hook.node_with_hooks(node_name=node_name)
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

        last_message = _messages[-1]

        if isinstance(last_message, ToolMessage):
            if last_message.name == "ask_clarification":
                return "human_feedback_node"

        # 检查LLM是否生成了工具调用指令
        if isinstance(last_message, AIMessage):
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                logger.info(
                    f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
                )
                return "tools"

        return "__end__"

    return route_edges


# ######################################################################################
# 编译图
def compile_super_nova_agent():

    # 节点和边
    tools = Digital_Human_Manager.copy()
    tools = [
        tools["ask_clarification"],
        tools["web_search"],
        tools["web_crawl"],
        tools["read_file"],
        tools["write_file"],
        tools["edit_file"],
        tools["glob"],
        tools["grep"],
        tools["ls"],
        tools["execute"],
        tools["write_todos"],
    ]

    super_nova_node = create_super_nova_node(tools=tools)
    human_feedback_node = create_human_feedback_node(node_name="human_feedback_node")
    tool_node = ToolNode(tools=tools)
    route_edges = create_route_tools_edges()

    # 构建图
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("super_nova_node", super_nova_node)
    _agent.add_node("human_feedback_node", human_feedback_node)
    _agent.add_node("tools", tool_node)
    _agent.add_edge(START, "super_nova_node")
    _agent.add_edge("tools", "super_nova_node")
    _agent.add_edge("human_feedback_node", "super_nova_node")
    _agent.add_conditional_edges(
        source="super_nova_node",
        path=route_edges,
        path_map={
            "tools": "tools",  # 路由到 tools 节点
            "human_feedback_node": "human_feedback_node",
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
