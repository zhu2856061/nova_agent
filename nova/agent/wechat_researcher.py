# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Annotated, Literal, cast

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    MessageLikeRepresentation,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel

from nova.llms import get_llm_by_type
from nova.prompts.wechat_researcher import apply_system_prompt_template
from nova.tools import wechat_searcher_tool
from nova.utils import (
    get_today_str,
    remove_up_to_last_ai_message,
    set_color,
)

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
@dataclass(kw_only=True)
class State:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    wechat_researcher_messages: Annotated[list[MessageLikeRepresentation], add_messages]
    tool_call_iterations: int = field(
        default=0,
        metadata={"description": "The number of iterations of tool calls."},
    )
    compressed_research: str = field(
        default="",
        metadata={"description": "The compressed research to use for the agent."},
    )


@dataclass(kw_only=True)
class Context:
    trace_id: str = field(
        default="default",
        metadata={"description": "The trace_id to use for the agent."},
    )
    wechat_researcher_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )
    max_react_tool_calls: int = field(
        default=5,
        metadata={"description": "The maximum number of tool calls to allow."},
    )


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


# ######################################################################################
async def wechat_researcher(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["wechat_researcher_tools", "__end__"]]:
    # 变量
    _trace_id = runtime.context.trace_id
    _model_name = runtime.context.wechat_researcher_model
    _messages = state.wechat_researcher_messages
    _tool_call_iterations = state.tool_call_iterations
    try:
        # 提示词
        def _assemble_prompt(messages):
            messages = [
                SystemMessage(
                    content=apply_system_prompt_template(
                        "wechat_researcher_system", {"date": get_today_str()}
                    )
                )
            ] + messages

            return messages

        # LLM
        def _get_llm():
            _tools = [wechat_searcher_tool, ResearchComplete]
            return get_llm_by_type(_model_name).bind_tools(_tools)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=researcher | message={response}", "pink"
            )
        )

        return Command(
            goto="wechat_researcher_tools",
            update={
                "wechat_researcher_messages": [response],
                "tool_call_iterations": _tool_call_iterations + 1,
            },
        )

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=researcher | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=researcher | error={e}"
            },
        )


async def wechat_researcher_tools(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["wechat_researcher", "compress_research", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _most_recent_message = state.wechat_researcher_messages[-1]
        _tool_call_iterations = state.tool_call_iterations
        _max_react_tool_calls = runtime.context.max_react_tool_calls

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
        tool_calls = cast(AIMessage, _most_recent_message).tool_calls
        coros = []
        for tool_call in tool_calls:
            tmp = {**tool_call["args"]}
            coros.append(execute_tool_safely(wechat_searcher_tool, tmp))
        observations = await asyncio.gather(*coros)

        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=researcher_tools | message=use execute_tool_safely: \n {str(observations)[:400]}... ",
                "pink",
            )
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
                    "wechat_researcher_messages": tool_outputs,
                },
            )

        return Command(
            goto="wechat_researcher",
            update={
                "wechat_researcher_messages": tool_outputs,
            },
        )

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=researcher_tools | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=researcher_tools | error={e}"
            },
        )


# 精炼结果
async def compress_research(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.wechat_researcher_model
        _messages = state.wechat_researcher_messages

        # 提示词
        def _assemble_prompt(messages):
            messages = (
                [
                    SystemMessage(
                        content=apply_system_prompt_template(
                            "compress_research_system", {"date": get_today_str()}
                        )
                    )
                ]
                + messages
                + [
                    HumanMessage(
                        content=apply_system_prompt_template("compress_research_human")
                    )
                ]
            )

            return messages

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        max_retries = 3
        current_retry = 0
        while current_retry <= max_retries:
            try:
                _tmp_messages = _assemble_prompt(_messages)
                response = await _get_llm().ainvoke(_tmp_messages)
                logger.info(
                    set_color(
                        f"trace_id={_trace_id} | node=compress_research | message=\n {str(response.content)[:500]}... ",
                        "pink",
                    )
                )
                return Command(
                    goto="__end__",
                    update={
                        "compressed_research": str(response.content),
                    },
                )
            except Exception as e:
                # 多个工具产生的结果，删除最后一个工具的结果
                _messages = remove_up_to_last_ai_message(_messages)
                logger.warning(f"remove_up_to_last_ai_message: {e}")
                current_retry += 1

        return Command(
            goto="__end__",
            update={
                "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
            },
        )
    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=researcher_tools | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=researcher_tools | error={e}"
            },
        )


# researcher subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("wechat_researcher", wechat_researcher)
_agent.add_node("wechat_researcher_tools", wechat_researcher_tools)
_agent.add_node("compress_research", compress_research)
_agent.add_edge(START, "wechat_researcher")

wechat_researcher_agent = _agent.compile()
