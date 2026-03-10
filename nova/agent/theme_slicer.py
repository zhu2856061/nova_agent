# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import json
import logging
import os
from typing import Annotated, List, cast

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova import CONF
from nova.hooks import Super_Agent_Hook_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.super_agent import SuperContext, SuperState
from nova.utils.log_utils import log_info_set_color

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量
class Topic(BaseModel):
    id: int = Field(
        description="Unique integer ID for the topic (start from 1 and increment sequentially)",
        gt=0,  # 确保ID为正整数
    )
    title: str = Field(
        description="Concise, clear title of the research topic (5-20 words)",
        min_length=5,
        max_length=50,
    )
    description: str = Field(
        description="Detailed research focus and content of the topic (50-200 words)",
        min_length=50,
        max_length=300,
    )
    keywords: List[str] = Field(
        description="3-5 core keywords for the topic (lowercase, no special characters)",
    )


TOPIC_DESCRIPTION = "Split writing outline into 3-8 independent research topics, return structured topic data in JSON format"


@tool("topic_slicer", description=TOPIC_DESCRIPTION)
async def topic_slicer_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[SuperContext, SuperState],
    topics: List[Topic],
):
    try:
        # 核心校验：确保主题数量符合3-8的要求
        if not 3 <= len(topics) <= 8:
            raise ValueError(
                f"Topic count must be between 3 and 8 (current: {len(topics)})"
            )

        # 校验每个Topic字段的合法性（Pydantic已自动校验，此处补充业务校验）
        for idx, topic in enumerate(topics):
            if len(topic.keywords) < 3 or len(topic.keywords) > 5:
                raise ValueError(
                    f"Topic {topic.id} has invalid keyword count (must be 3-5)"
                )

        tmp = [topic.model_dump() for topic in topics]

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        json.dumps({"topics": tmp}, ensure_ascii=False),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    except Exception as e:
        return Command(
            update={
                "code": -1,
                "messages": [
                    ToolMessage(
                        f"Error: Unexpected error: {type(e).__name__}: {e}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
        # return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ######################################################################################
# 创建主题挖掘节点
def create_theme_slicer_node(node_name, tools=None, structured_output=None):

    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 核心：组装提示词
        user_guidance = state.get("user_guidance")
        _human_in_loop_value = (
            user_guidance.get("human_in_loop_value", "") if user_guidance else ""
        )
        _messages = cast(list[AnyMessage], state.get("messages"))
        tmp = {
            "content": get_buffer_string(_messages),
            "user_guidance": _human_in_loop_value,
        }

        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "theme", "theme_slicer"
        )
        return [
            HumanMessage(
                content=Prompts_Provider_Instance.prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ]

    async def _after_model_hooks(
        state: SuperState, runtime: Runtime[SuperContext], response: AIMessage
    ):

        # 去掉冗余信息
        response.additional_kwargs = {}
        response.response_metadata = {}

        return Command(
            update={"messages": [response]},
        )

    @Super_Agent_Hook_Instance.node_with_hooks(node_name="theme_slicer")
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")

        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})
        # 创建工作目录
        _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
        _work_dir = os.path.join(cast(str, _task_dir), _thread_id)
        # os.makedirs(_work_dir, exist_ok=True)

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

        if isinstance(_messages[-1], ToolMessage):
            return Command(
                goto="__end__",
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

        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})
        # 创建工作目录
        _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
        _work_dir = os.path.join(cast(str, _task_dir), _thread_id)
        # os.makedirs(_work_dir, exist_ok=True)

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
                "content": "对生成的topic进行确定",
            }
        )
        log_info_set_color(_thread_id, "human_feedback", value)

        return Command(
            update={
                "user_guidance": {"human_in_loop_value": value["human_in_loop"]},
            },
        )

    return _node


# 创建路由[ 反馈 ···> 主题 | END ]条件边
def create_route_human_feedback_edges():
    """创建路由逻辑, 主要是路由到工具还是结束"""

    # 4. 定义路由逻辑：判断是否需要调用工具
    def route_edges(state: SuperState, runtime: Runtime[SuperContext]):
        """
        路由规则：
        - 根据用户的反馈，若是 内容=“确定或者1”，则跳转到 END
        - 若是 内容!=“确定或者1”，则跳转到 主题挖掘
        """

        _code = state.get("code", 0)
        if _code != 0:
            return "__end__"

        user_guidance = state.get("user_guidance")
        _human_in_loop_value = (
            user_guidance.get("human_in_loop_value", "") if user_guidance else ""
        )

        if not _human_in_loop_value:
            return "__end__"

        if _human_in_loop_value == "确定" or _human_in_loop_value == "1":
            return "__end__"
        else:
            return "theme_slicer_node"

    return route_edges


# 创建路由[ 主题 ···> 反馈 | tools ]条件边
def create_route_theme_slicer_edges():
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

        logger.info(f"[{_thread_id}]: _messages: {_messages[-1]}")
        if isinstance(_messages[-1], ToolMessage):
            return "human_feedback_node"
        if not isinstance(_messages[-1], AIMessage):
            return "__end__"

        last_message = cast(AIMessage, _messages[-1])

        # 检查LLM是否生成了工具调用指令
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
            )
            return "tools"

        return "human_feedback_node"

    return route_edges


# ######################################################################################
# 编译图
def compile_theme_slicer_agent():
    tools = [topic_slicer_tool]
    # 节点和边
    theme_slicer_node = create_theme_slicer_node(node_name="theme_slicer", tools=tools)
    human_feedback_node = create_human_feedback_node(node_name="human_feedback_node")
    tool_node = ToolNode(tools=tools)

    human_feedback_route_edges = create_route_human_feedback_edges()
    theme_slicer_route_edges = create_route_theme_slicer_edges()

    # 构建图
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("theme_slicer_node", theme_slicer_node)
    _agent.add_node("human_feedback_node", human_feedback_node)
    _agent.add_node("tools", tool_node)

    _agent.add_edge(START, "theme_slicer_node")
    _agent.add_edge("tools", "theme_slicer_node")

    _agent.add_conditional_edges(
        source="theme_slicer_node",
        path=theme_slicer_route_edges,
        path_map={
            "human_feedback_node": "human_feedback_node",
            "tools": "tools",
            "__end__": "__end__",  # 结束流程
        },
    )
    _agent.add_conditional_edges(
        source="human_feedback_node",
        path=human_feedback_route_edges,
        path_map={
            "theme_slicer_node": "theme_slicer_node",
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    _agent = _agent.compile(checkpointer=checkpointer)
    png_bytes = _agent.get_graph(xray=True).draw_mermaid()
    logger.info(f"theme_slicer_agent: \n\n{png_bytes}")
    return _agent
