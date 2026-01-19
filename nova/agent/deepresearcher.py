# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
import os
from typing import Annotated, Literal

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field

from nova import CONF
from nova.agent.researcher import researcher_agent
from nova.agent.utils import extract_valid_info, node_with_hooks
from nova.llms import get_llm_by_type, llm_with_hooks
from nova.model.agent import Context, Messages, State
from nova.prompts.template import apply_prompt_template, get_prompt
from nova.tools.format_result import markdown_to_html_tool
from nova.utils.common import get_today_str, override_reducer
from nova.utils.log_utils import log_error_set_color, log_info_set_color

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


# clarify_with_user uses this
class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )


# write_research_brief uses this
class ResearchQuestion(BaseModel):
    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )


# supervisor uses this
class ConductResearch(BaseModel):
    """Call this tool to conduct research on a specific topic."""

    research_topic: str = Field(
        description="The topic to research. Should be a single topic, and should be described in high detail (at least a paragraph).",
    )


# supervisor uses this
class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


class ResearcherOutputState(BaseModel):
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer]


# ######################################################################################
# 函数


# 用户澄清
async def clarify_with_user(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["write_research_brief", "__end__"]]:
    _NODE_NAME = "clarify_with_user"
    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _messages = state.messages.value

    # 提示词
    def _assemble_prompt(messages):
        tmp = {"messages": get_buffer_string(messages), "date": get_today_str()}
        _prompt_tamplate = get_prompt("researcher", "clarify_with_user")
        return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

    # 4 大模型
    response = await llm_with_hooks(
        _thread_id, _NODE_NAME, _assemble_prompt(_messages), _model_name
    )

    if not isinstance(response, ClarifyWithUser):
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": "ClarifyWithUser is not a valid response",
                "messages": Messages(type="end"),
            },
        )

    if response.need_clarification:
        return Command(
            goto="__end__",
            update={
                "code": 0,
                "err_message": "ok",
                "messages": Messages(type="end"),
                "data": {_NODE_NAME: response.model_dump()},
            },
        )
    else:
        return Command(
            goto="write_research_brief",
            update={
                "code": 0,
                "err_message": "ok",
                "messages": [HumanMessage(content=response.verification)],
                "data": {_NODE_NAME: response.model_dump()},
            },
        )


# 转换问题
async def write_research_brief(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["supervisor", "__end__"]]:
    _NODE_NAME = "write_research_brief"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _messages = state.messages.value

    # 提示词
    def _assemble_prompt(messages):
        tmp = {"messages": get_buffer_string(messages), "date": get_today_str()}

        _prompt_tamplate = get_prompt("researcher", "write_research_brief")
        return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

    # 4 大模型
    response = await llm_with_hooks(
        _thread_id,
        _NODE_NAME,
        _assemble_prompt(_messages),
        _model_name,
        structured_output=[ResearchQuestion],
    )

    if not isinstance(response, ResearchQuestion):
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": "ResearchQuestion is not a valid response",
                "messages": Messages(type="end"),
            },
        )
    state.user_guidance["research_brief"] = response.research_brief
    return Command(
        goto="supervisor",
        update={
            "code": 0,
            "err_message": "ok",
            "messages": Messages(
                type="override",
                value=[HumanMessage(content=response.research_brief)],
            ),
            "user_guidance": state.user_guidance,
        },
    )


# 监督员
async def supervisor(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["supervisor_tools", "__end__"]]:
    _NODE_NAME = "supervisor"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model

    _max_concurrent = runtime.context.config.get("max_concurrent_research_units", 2)
    _messages = state.messages.value
    _research_iterations = state.user_guidance.get("research_iterations", 1)

    if not _messages:
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": "messages is not found",
                "messages": Messages(type="end"),
            },
        )

    # 提示词
    def _assemble_prompt():
        tmp = {
            "max_concurrent_research_units": _max_concurrent,
            "date": get_today_str(),
        }
        _prompt_tamplate = get_prompt("researcher", "supervisor_system")
        return [
            SystemMessage(content=apply_prompt_template(_prompt_tamplate, tmp)),
        ] + _messages

    # 4 大模型
    response = await llm_with_hooks(
        _thread_id,
        _NODE_NAME,
        _assemble_prompt(),
        _model_name,
        tools=[ConductResearch, ResearchComplete],
    )

    extract_valid_info(response)

    state.user_guidance["research_iterations"] = _research_iterations + 1
    return Command(
        goto="supervisor_tools",
        update={
            "messages": response,
            "user_guidance": state.user_guidance,
            "data": {_NODE_NAME: response},
        },
    )


# 监督员工具
async def supervisor_tools(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["final_report_generation", "supervisor", "__end__"]]:
    _NODE_NAME = "supervisor_tools"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model

    _max_concurrent = runtime.context.config.get("max_concurrent_research_units", 2)
    _max_researcher_iterations = runtime.context.config.get(
        "max_researcher_iterations", 3
    )
    _supervisor = state.data.get("supervisor")
    _research_iterations = state.user_guidance["research_iterations"]

    # 执行
    exceeded_allowed_iterations = _research_iterations >= _max_researcher_iterations
    no_tool_calls = not _supervisor.tool_calls  # type: ignore
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in _supervisor.tool_calls  # type: ignore
    )

    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(goto="final_report_generation")

    all_conduct_research_calls = [
        tool_call
        for tool_call in _supervisor.tool_calls  # type: ignore
        if tool_call["name"] == "ConductResearch"
    ]
    conduct_research_calls = all_conduct_research_calls[:_max_concurrent]
    overflow_conduct_research_calls = all_conduct_research_calls[_max_concurrent:]

    coros = []
    for tool_call in conduct_research_calls:
        coros.append(
            researcher_agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(content=tool_call["args"]["research_topic"]),
                    ],
                },  # type: ignore
                context={
                    "thread_id": _thread_id,
                    "model": _model_name,
                },  # type: ignore
            )
        )
        log_info_set_color(
            _thread_id,
            _NODE_NAME,
            f"use researcher_subgraph: \n tool_call_id: {tool_call['id']}\n tool_args: {tool_call['args']} ",
        )

    tool_results = await asyncio.gather(*coros)
    tool_messages = [
        ToolMessage(
            content=observation.get(
                "compressed_research",
                "Error synthesizing research report: Maximum retries exceeded",
            ),
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
        for observation, tool_call in zip(tool_results, conduct_research_calls)
    ]

    # Handle any tool calls made > max_concurrent_research_units
    for overflow_conduct_research_call in overflow_conduct_research_calls:
        tool_messages.append(
            ToolMessage(
                content=f"Error: Did not run this research as you have already exceeded the maximum number of concurrent research units. Please try again with {_max_concurrent} or fewer research units.",
                name="ConductResearch",
                tool_call_id=overflow_conduct_research_call["id"],
            )
        )
    # raw_notes_concat = "\n".join(
    #     [
    #         "\n".join(observation.get("raw_notes", []))
    #         for observation in tool_results
    #     ]
    # )
    return Command(
        goto="supervisor",
        update={
            "messages": tool_messages,
            # "data": {_NODE_NAME: raw_notes_concat},
        },
    )


# 报告员
async def final_report_generation(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    _NODE_NAME = "final_report_generation"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
    _model_name = runtime.context.model
    _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # _supervisor = state.data.get("supervisor")
    _research_brief = state.user_guidance.get("research_brief")
    _messages = state.messages.value

    if _messages is None or _research_brief is None:
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": "Missing supervisor or research_brief",
                "messages": Messages(type="end"),
            },
        )

    # 提示词
    def _assemble_prompt(findings):
        tmp = {
            "date": get_today_str(),
            "research_brief": _research_brief,
            "findings": findings,
        }

        _prompt_tamplate = get_prompt("researcher", "final_report_generation")
        return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

    # LLM
    findings = get_buffer_string(_messages)  # type: ignore
    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:
        try:
            final_report = await llm_with_hooks(
                _thread_id, _NODE_NAME, _assemble_prompt(findings), _model_name
            )

            await markdown_to_html_tool.arun(
                {
                    "md_content": final_report.content,
                    "output_file": os.path.join(_work_dir, "final_report.html"),
                }
            )

            return Command(
                goto="__end__",
                update={
                    "code": 0,
                    "err_message": "ok",
                    "messages": Messages(type="end"),
                    "user_guidance": state.user_guidance,
                    "data": {_NODE_NAME: final_report.content},
                },
            )

        except Exception:
            findings_token_limit = int(len(findings) * 0.9)
            logger.warning(f"Reducing the chars to {findings_token_limit}")
            findings = findings[:findings_token_limit]
            current_retry += 1

    return Command(
        goto="__end__",
        update={
            "code": 1,
            "err_message": "Error generating final report: Maximum retries exceeded",
            "messages": Messages(type="end"),
        },
    )


#
# Agent - Workflow
graph_builder = StateGraph(State, context_schema=Context)
graph_builder.add_node("clarify_with_user", clarify_with_user)
graph_builder.add_node("write_research_brief", write_research_brief)
graph_builder.add_node("supervisor", supervisor)
graph_builder.add_node("supervisor_tools", supervisor_tools)
graph_builder.add_node("final_report_generation", final_report_generation)
graph_builder.add_edge(START, "clarify_with_user")


checkpointer = InMemorySaver()
deepresearcher = graph_builder.compile(checkpointer=checkpointer)
# deepresearcher = graph_builder.compile()
png_bytes = deepresearcher.get_graph(xray=True).draw_mermaid()
logger.info(f"ainovel_architecture_agent: \n\n{png_bytes}")
