# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
import operator
from typing import Annotated, Literal

from langchain_core.messages import (
    HumanMessage,
    MessageLikeRepresentation,
    SystemMessage,
    ToolMessage,
    filter_messages,
)
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import TypedDict

from nova.llms import get_llm_by_type
from nova.prompts.researcher import apply_system_prompt_template
from nova.tools import search_tool
from nova.utils import (
    get_today_str,
    override_reducer,
    remove_up_to_last_ai_message,
    set_color,
)

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
class ResearcherState(TypedDict):
    err_message: str
    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer]


class Context(TypedDict):
    trace_id: str

    researcher_model: str
    summarize_model: str
    compress_research_model: str

    max_react_tool_calls: int


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


# ######################################################################################
# 函数


# 研究员
async def researcher(
    state: ResearcherState, runtime: Runtime[Context]
) -> Command[Literal["researcher_tools", "__end__"]]:
    # 变量
    _trace_id = runtime.context.get("trace_id", "default")
    _model_name = runtime.context.get("researcher_model", "basic")
    _messages = state.get("researcher_messages")
    _tool_call_iterations = state.get("tool_call_iterations", 0)
    try:
        # 提示词
        def _assemble_prompt(messages):
            messages = [
                SystemMessage(
                    content=apply_system_prompt_template(
                        "researcher_system", {"date": get_today_str()}
                    )
                )
            ] + messages

            return messages

        # LLM
        def _get_llm():
            _tools = [search_tool, ResearchComplete]
            return get_llm_by_type(_model_name).bind_tools(_tools)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=researcher | message={response}", "pink"
            )
        )

        return Command(
            goto="researcher_tools",
            update={
                "researcher_messages": [response],
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


# 研究员工具
async def researcher_tools(
    state: ResearcherState, runtime: Runtime[Context]
) -> Command[Literal["researcher", "compress_research", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.get("trace_id", "default")
        _model_name = runtime.context.get("summarize_model", "basic")
        _most_recent_message = state.get("researcher_messages")[-1]
        _tool_call_iterations = state.get("tool_call_iterations", 0)
        _max_react_tool_calls = runtime.context.get("max_react_tool_calls", 5)

        # 执行
        if not _most_recent_message.tool_calls or any(  # type: ignore
            tool_call["name"] == "ResearchComplete"
            for tool_call in _most_recent_message.tool_calls  # type: ignore
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
        tool_calls = _most_recent_message.tool_calls  # type: ignore
        coros = []
        for tool_call in tool_calls:
            tmp = {**tool_call["args"], "runtime": {"summarize_model": _model_name}}
            coros.append(execute_tool_safely(search_tool, tmp))

        observations = await asyncio.gather(*coros)

        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=researcher_tools | message=use execute_tool_safely: \n {observations} ",
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
                    "researcher_messages": tool_outputs,
                },
            )

        return Command(
            goto="researcher",
            update={
                "researcher_messages": tool_outputs,
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
    state: ResearcherState, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.get("trace_id", "default")
        _model_name = runtime.context.get("compress_research_model", "basic")
        _messages = state.get("researcher_messages", [])

        # 提示词
        def _assemble_prompt(messages):
            messages = [
                SystemMessage(
                    content=apply_system_prompt_template(
                        "compress_research_system", {"date": get_today_str()}
                    )
                )
            ] + messages

            messages.append(
                HumanMessage(
                    content=apply_system_prompt_template("compress_research_human")
                )
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
                        f"trace_id={_trace_id} | node=compress_research | message=\n {str(response.content)} ",
                        "pink",
                    )
                )
                return Command(
                    goto="__end__",
                    update={
                        "compressed_research": str(response.content),
                        "raw_notes": [
                            "\n".join(
                                [
                                    str(m.content)
                                    for m in filter_messages(
                                        _tmp_messages, include_types=["tool", "ai"]
                                    )
                                ]
                            )
                        ],
                    },
                )
            except Exception as e:
                _messages = remove_up_to_last_ai_message(_messages)
                logger.warning(f"remove_up_to_last_ai_message: {e}")
                current_retry += 1
        return Command(
            goto="__end__",
            update={
                "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
                "raw_notes": [
                    "\n".join(
                        [
                            str(m.content)
                            for m in filter_messages(
                                _messages, include_types=["tool", "ai"]
                            )
                        ]
                    )
                ],
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
_agent = StateGraph(ResearcherState, context_schema=Context)
_agent.add_node("researcher", researcher)
_agent.add_node("researcher_tools", researcher_tools)
_agent.add_node("compress_research", compress_research)
_agent.add_edge(START, "researcher")

researcher_agent = _agent.compile()
