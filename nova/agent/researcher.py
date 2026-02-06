# -*- coding: utf-8 -*-
# @Time   : 2025/09/16 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
from typing import Literal, cast

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel

from nova.agent.utils import extract_valid_info, node_with_hooks
from nova.llms import llm_with_hooks
from nova.model.agent import Context, Messages, State
from nova.llms.template import apply_prompt_template, get_prompt
from nova.tools.llm_searcher import llm_searcher_tool
from nova.tools.wechat_searcher import wechat_searcher_tool
from nova.utils.common import get_today_str, remove_up_to_last_ai_message
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


# 研究员
async def researcher(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["researcher_tools", "__end__"]]:
    _NODE_NAME = "researcher"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _messages = state.messages.value
    _tool_call_iterations = state.user_guidance.get("tool_call_iterations", 0)

    # 提示词
    def _assemble_prompt(messages):
        tmp = {
            "date": get_today_str(),
        }
        _prompt_tamplate = get_prompt("researcher", "researcher_system")
        return [
            SystemMessage(content=apply_prompt_template(_prompt_tamplate, tmp))
        ] + messages

    # 4 大模型
    response = await llm_with_hooks(
        _thread_id,
        _NODE_NAME,
        _assemble_prompt(_messages),
        _model_name,
        tools=[llm_searcher_tool, ResearchComplete],
    )
    extract_valid_info(response)

    state.user_guidance["tool_call_iterations"] = _tool_call_iterations + 1

    return Command(
        goto="researcher_tools",
        update={
            "code": 0,
            "err_message": "ok",
            "messages": Messages(type="add", value=[response]),
            "user_guidance": state.user_guidance,
            "data": {_NODE_NAME: response},
        },
    )


# 研究员工具
async def researcher_tools(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["compress_research", "researcher", "__end__"]]:
    _NODE_NAME = "researcher_tools"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _tool_call_iterations = state.user_guidance.get("tool_call_iterations", 1)
    _max_react_tool_calls = state.user_guidance.get("max_react_tool_calls", 1)
    _most_recent_message = state.data.get("researcher")

    # 执行
    if not cast(AIMessage, _most_recent_message).tool_calls or any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in cast(AIMessage, _most_recent_message).tool_calls
    ):
        return Command(
            goto="compress_research",
        )

    async def execute_tool_safely(tool, args):
        try:
            return await tool.ainvoke(args)
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    # Otherwise, execute tools and gather results.
    tool_calls = cast(AIMessage, _most_recent_message).tool_calls  # type: ignore
    coros = []
    for tool_call in tool_calls:
        tmp = {**tool_call["args"], "runtime": {"summarize_model": _model_name}}
        coros.append(execute_tool_safely(llm_searcher_tool, tmp))
    observations = await asyncio.gather(*coros)

    log_info_set_color(
        _thread_id,
        _NODE_NAME,
        f"use execute_tool_safely: \n {str(observations)[:400]} ",
    )

    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
        for observation, tool_call in zip(observations, tool_calls)
    ]

    if _tool_call_iterations >= _max_react_tool_calls:
        return Command(
            goto="compress_research",
            update={
                "messages": tool_outputs,
            },
        )

    return Command(
        goto="researcher",
        update={
            "messages": tool_outputs,
        },
    )


# 研究员工具
async def wechat_researcher_tools(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["compress_research", "researcher", "__end__"]]:
    _NODE_NAME = "researcher_tools"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _tool_call_iterations = state.user_guidance.get("tool_call_iterations", 1)
    _max_react_tool_calls = state.user_guidance.get("max_react_tool_calls", 1)
    _most_recent_message = state.data.get("researcher")

    # 执行
    if not cast(AIMessage, _most_recent_message).tool_calls or any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in cast(AIMessage, _most_recent_message).tool_calls
    ):
        return Command(
            goto="compress_research",
        )

    async def execute_tool_safely(tool, args):
        try:
            return await tool.ainvoke(args)
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    # Otherwise, execute tools and gather results.
    tool_calls = cast(AIMessage, _most_recent_message).tool_calls  # type: ignore
    coros = []
    for tool_call in tool_calls:
        tmp = {**tool_call["args"], "runtime": {"summarize_model": _model_name}}
        coros.append(execute_tool_safely(wechat_searcher_tool, tmp))
    observations = await asyncio.gather(*coros)

    log_info_set_color(
        _thread_id,
        _NODE_NAME,
        f"use execute_tool_safely: \n {str(observations)[:400]} ",
    )

    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
        for observation, tool_call in zip(observations, tool_calls)
    ]

    if _tool_call_iterations >= _max_react_tool_calls:
        return Command(
            goto="compress_research",
            update={
                "messages": tool_outputs,
            },
        )

    return Command(
        goto="researcher",
        update={
            "messages": tool_outputs,
        },
    )


# 精炼结果
async def compress_research(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    _NODE_NAME = "compress_research"
    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _messages = state.messages.value

    # 提示词
    def _assemble_prompt(messages):
        _compress_research_system = get_prompt("researcher", "compress_research_system")
        messages = [
            SystemMessage(
                content=apply_prompt_template(
                    _compress_research_system, {"date": get_today_str()}
                )
            )
        ] + messages

        _compress_research_human = get_prompt("researcher", "compress_research_human")
        messages.append(
            HumanMessage(content=apply_prompt_template(_compress_research_human))
        )
        return messages

    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:  # 尝试3次, 防止因为上下文过长，导致失败
        try:
            # 4 大模型
            response = await llm_with_hooks(
                _thread_id,
                _NODE_NAME,
                _assemble_prompt(_messages),
                _model_name,
            )

            extract_valid_info(response)
            log_info_set_color(_thread_id, _NODE_NAME, response.content)

            return Command(
                goto="__end__",
                update={
                    "code": 0,
                    "messages": Messages(type="end"),
                    "data": {_NODE_NAME: response.content},
                },
            )
        except Exception as e:
            _messages = remove_up_to_last_ai_message(_messages)
            logger.warning(f"remove_up_to_last_ai_message: {e}")
            current_retry += 1

    return Command(
        goto="__end__",
        update={
            "code": 1,
            "messages": Messages(type="end"),
            "data": {
                _NODE_NAME: "Error synthesizing research report: Maximum retries exceeded"
            },
        },
    )


def compile_researcher_agent():
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node("researcher", node_with_hooks(researcher, "researcher"))
    _agent.add_node(
        "researcher_tools", node_with_hooks(researcher_tools, "researcher_tools")
    )
    _agent.add_node(
        "compress_research", node_with_hooks(compress_research, "compress_research")
    )
    _agent.add_edge(START, "researcher")
    return _agent.compile()


def compile_wechat_researcher_agent():
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node("researcher", node_with_hooks(researcher, "researcher"))
    _agent.add_node(
        "researcher_tools", node_with_hooks(wechat_researcher_tools, "researcher_tools")
    )
    _agent.add_node(
        "compress_research", node_with_hooks(compress_research, "compress_research")
    )
    _agent.add_edge(START, "researcher")
    return _agent.compile()


researcher_agent = compile_researcher_agent()
wechat_researcher_agent = compile_wechat_researcher_agent()
