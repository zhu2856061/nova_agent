# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
import uuid
from typing import Annotated, cast

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command

from nova import CONF
from nova.hooks import Super_Agent_Hook_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.memory import SQLITESTORE
from nova.model.super_agent import SuperContext, SuperState
from nova.utils.common import get_today_str

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################
# 函数

TOPIC_DESCRIPTION = """Upsert a memory in the database.

    If a memory conflicts with an existing one, then just UPDATE the
    existing one by passing in memory_id - don't create two memories
    that are the same. If the user corrects a memory, UPDATE it.

    Args:
        content: The main content of the memory. For example:
            "User expressed interest in learning about French."
        context: Additional context for the memory. For example:
            "This was mentioned while discussing career options in Europe."
        memory_id: ONLY PROVIDE IF UPDATING AN EXISTING MEMORY.
        The memory to overwrite.
"""


@tool("upsert_memory", description=TOPIC_DESCRIPTION)
async def upsert_memory_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[SuperContext, SuperState],
    content: str,
    context: str,
):

    mem_id = uuid.uuid4()
    _config = runtime.context.get("config")
    _user_id = _config.get("user_id")  # type: ignore

    await SQLITESTORE.aput(
        ("memories", cast(str, _user_id)),
        key=str(mem_id),
        value={"content": content, "context": context},
    )

    return f"Stored memory {mem_id}"


# 创建路由[ 记忆 ···> tools | END ]条件边
def create_memorizer_route_edges():
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

        if not isinstance(_messages[-1], AIMessage):
            return "__end__"

        last_message = cast(AIMessage, _messages[-1])

        # 检查LLM是否生成了工具调用指令
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
            )
            return "tools"

        return "__end__"

    return route_edges


# ######################################################################################
# 创建记忆节点
def create_memorizer_node(node_name, tools=None, structured_output=None):

    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 核心：组装提示词
        _config = runtime.context.get("config")

        _user_id = _config.get("user_id")  # type: ignore

        _messages = cast(list[AnyMessage], state.get("messages"))

        memories = await cast(BaseStore, SQLITESTORE).asearch(
            ("memories", cast(str, _user_id)),
            query=str([m.content for m in _messages[-3:]]),  # type: ignore
            limit=10,
        )

        # Format memories for inclusion in the prompt
        tmp = {
            "user_info": "\n".join(f"[{mem.key}]: {mem.value}" for mem in memories),
            "date": get_today_str(),
        }

        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "memorizer", "memorizer"
        )
        return [
            SystemMessage(
                content=Prompts_Provider_Instance.prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ] + _messages

    async def _after_model_hooks(
        state: SuperState, runtime: Runtime[SuperContext], response: AIMessage
    ):

        # 去掉冗余信息
        response.additional_kwargs = {}
        response.response_metadata = {}

        return Command(
            update={"messages": [response]},
        )

    @Super_Agent_Hook_Instance.node_with_hooks(node_name="memorizer")
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


def compile_memorizer_agent():

    tools = [upsert_memory_tool]
    # 节点和边
    memorizer_node = create_memorizer_node(node_name="memorizer", tools=tools)
    tool_node = ToolNode(tools=tools)

    memorizer_route_edges = create_memorizer_route_edges()

    # researcher subgraph
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("memorizer_node", memorizer_node)
    _agent.add_node("tools", tool_node)
    _agent.add_edge(START, "memorizer_node")

    _agent.add_conditional_edges(
        source="memorizer_node",
        path=memorizer_route_edges,
        path_map={
            "tools": "tools",
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    _agent = _agent.compile(checkpointer=checkpointer)
    png_bytes = _agent.get_graph(xray=True).draw_mermaid()
    logger.info(f"memorizer_agent: \n\n{png_bytes}")
    return _agent
