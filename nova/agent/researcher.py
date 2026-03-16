# -*- coding: utf-8 -*-
# @Time   : 2025/09/16 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite
from pydantic import BaseModel

from nova.model.super_agent import SuperContext, SuperState
from nova.provider import get_llms_provider, get_prompts_provider, get_super_agent_hooks
from nova.tools import llm_searcher_tool, wechat_searcher_tool
from nova.utils.common import (
    get_today_str,
    remove_up_to_last_ai_message,
    truncate_if_too_long,
)
from nova.utils.log_utils import log_info_set_color

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


# ######################################################################################
# 函数


def create_researcher_node(
    node_name="researcher",
    *,
    prompt_dir="researcher",
    prompt_name="researcher",
    tools=None,
    structured_output=None,
):
    _hook = get_super_agent_hooks()

    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 核心：组装提示词
        _messages = cast(list[AnyMessage], state.get("messages"))

        tmp = {
            "date": get_today_str(),
        }
        _prompt_tamplate = get_prompts_provider().get_template(prompt_dir, prompt_name)

        return [
            SystemMessage(
                content=get_prompts_provider().prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ] + _messages

    @staticmethod
    async def _after_model_hooks(
        response: AIMessage, state: SuperState, runtime: Runtime[SuperContext]
    ):
        _thread_id = runtime.context.get("thread_id", "default")
        logger.info(
            f"_thread_id={_thread_id}, result: {truncate_if_too_long(str(response))}"
        )
        if not isinstance(response, AIMessage):
            return Command(
                update={
                    "code": 1,
                    "err_message": "response type not AIMessage",
                    "messages": [response],
                },
            )
        # 去掉冗余信息
        response.additional_kwargs = {}
        response.response_metadata = {}
        return response

    @_hook.node_with_hooks(node_name="researcher")
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

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
        if state.get("data") is None:
            _tool_call_iterations = 0
            _max_react_tool_calls = 3
        else:
            _tool_call_iterations = cast(dict, state.get("data")).get(
                "tool_call_iterations", 0
            )
            _max_react_tool_calls = cast(dict, state.get("data")).get(
                "max_react_tool_calls", 3
            )
        if _tool_call_iterations + 1 >= _max_react_tool_calls:
            return Command(goto="__end__")

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
        response = await _after_model_hooks(response, state, runtime)
        return Command(
            update={
                "messages": [response],
                "data": {
                    "result": response.content,
                    "tool_call_iterations": _tool_call_iterations + 1,
                },
            },
        )

    return _node


def create_compress_node(
    node_name="compress",
    *,
    tools=None,
    structured_output=None,
):
    _hook = get_super_agent_hooks()

    async def _before_model_hooks(_messages):
        # 核心：组装提示词

        _compress_research_system = get_prompts_provider().get_template(
            "researcher", "compress_research_system"
        )
        messages = [
            SystemMessage(
                content=get_prompts_provider().prompt_apply_template(
                    _compress_research_system, {"date": get_today_str()}
                )
            )
        ] + _messages

        _compress_research_human = get_prompts_provider().get_template(
            "researcher", "compress_research_human"
        )
        messages.append(
            HumanMessage(
                content=get_prompts_provider().prompt_apply_template(
                    _compress_research_human
                )
            )
        )
        return messages

    @_hook.node_with_hooks(node_name="compress")
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

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
        response = await _before_model_hooks(_messages)

        max_retries = 3
        current_retry = 0
        while current_retry <= max_retries:  # 尝试3次, 防止因为上下文过长，导致失败
            try:
                # 4 大模型
                response = await get_llms_provider().llm_wrap_hooks(
                    _thread_id,
                    node_name,
                    response,
                    _model_name,
                    tools=tools,
                    structured_output=structured_output,
                    **_config,  # type: ignore
                )
                log_info_set_color(_thread_id, node_name, response.content)

                return Command(
                    goto="__end__",
                    update={
                        "messages": Overwrite([response]),
                        "data": {"result": response.content},
                    },
                )
            except Exception as e:
                _messages = remove_up_to_last_ai_message(_messages)  # type: ignore
                logger.warning(f"remove_up_to_last_ai_message: {e}")
                current_retry += 1

    return _node


# 创建路由[ researcher ···> compress_node | tools | end]条件边
def create_researcher_route_edges():
    """创建路由[ researcher ···> compress | tools | end ]条件边"""

    # 4. 定义路由逻辑：判断是否需要调用工具
    def route_edges(state: SuperState, runtime: Runtime[SuperContext]):
        """
        路由规则：
        - 如果最后一条消息包含 tool_calls → 跳转到 tools 节点
        -
        - 否则 → compress
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
            return "compress_node"

        last_message = cast(AIMessage, _messages[-1])

        # 检查LLM是否生成了工具调用指令
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
            )
            return "tools"

        return "compress_node"

    return route_edges


def compile_researcher_agent():
    tools = [llm_searcher_tool]

    researcher_node = create_researcher_node()
    tool_node = ToolNode(tools=tools)
    compress_node = create_compress_node()

    researcher_route_edges = create_researcher_route_edges()

    _agent = StateGraph(SuperContext, context_schema=SuperContext)
    _agent.add_node("researcher_node", researcher_node)
    _agent.add_node("compress_node", compress_node)

    _agent.add_node("tools", tool_node)

    _agent.add_edge(START, "researcher_node")

    _agent.add_conditional_edges(
        source="researcher_node",
        path=researcher_route_edges,
        path_map={
            "tools": "tools",
            "compress_node": "compress_node",
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    _agent = _agent.compile(checkpointer=checkpointer)
    png_bytes = _agent.get_graph(xray=True).draw_mermaid()
    logger.info(f"researcher_agent: \n\n{png_bytes}")
    return _agent
