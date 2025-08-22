# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
import os
from typing import Annotated, Literal, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    MessageLikeRepresentation,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from core.agent.researcher import ResearcherAgent
from core.llms import get_llm_by_type
from core.prompts.deep_researcher import apply_system_prompt_template
from core.tools import markdown_to_html_tool
from core.utils import (
    get_notes_from_tool_calls,
    get_today_str,
    override_reducer,
    set_color,
)

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


class AgentState(MessagesState):
    err_message: str
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: Optional[str]
    raw_notes: Annotated[list[str], override_reducer]
    notes: Annotated[list[str], override_reducer]
    final_report: str


class SupervisorState(TypedDict):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str
    notes: Annotated[list[str], override_reducer]
    research_iterations: int
    raw_notes: Annotated[list[str], override_reducer]


class Context(TypedDict):
    trace_id: str
    task_dir: str

    clarify_model: str
    research_brief_model: str
    supervisor_model: str
    researcher_model: str
    summarize_model: str
    compress_research_model: str
    report_model: str

    max_concurrent_research_units: int
    max_react_tool_calls: int


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
    state: AgentState, runtime: Runtime[Context]
) -> Command[Literal["write_research_brief", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.get("trace_id", "default")
        _model_name = runtime.context.get("clarify_model", "basic")
        _messages = state["messages"]

        # 提示词
        def _assemble_prompt(messages):
            tmp = {"messages": get_buffer_string(messages), "date": get_today_str()}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("clarify_with_user", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ClarifyWithUser)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=clarify_with_user | message={response}",
                "pink",
            )
        )
        if response.need_clarification:  # type: ignore
            return Command(
                goto="__end__",
                update={"messages": [AIMessage(content=response.question)]},  # type: ignore
            )
        else:
            return Command(
                goto="write_research_brief",
                update={"messages": [AIMessage(content=response.verification)]},  # type: ignore
            )
    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=clarify_with_user | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=clarify_with_user | error={e}"
            },
        )


# 转换问题
async def write_research_brief(
    state: AgentState, runtime: Runtime[Context]
) -> Command[Literal["research_supervisor", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.get("trace_id", "default")
        _model_name = runtime.context.get("research_brief_model", "basic")
        _messages = state["messages"]

        # 提示词
        def _assemble_prompt(messages):
            tmp = {"messages": get_buffer_string(messages), "date": get_today_str()}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("write_research_brief", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ResearchQuestion)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=write_research_brief | message={response}",
                "pink",
            )
        )

        return Command(
            goto="research_supervisor",
            update={
                "research_brief": response.research_brief,  # type: ignore
                "supervisor_messages": {
                    "type": "override",
                    "value": [
                        HumanMessage(content=response.research_brief),  # type: ignore
                    ],
                },
            },
        )
    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=write_research_brief | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=write_research_brief | error={e}"
            },
        )


# 监督员
async def supervisor(
    state: SupervisorState, runtime: Runtime[Context]
) -> Command[Literal["supervisor_tools", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.get("trace_id", "default")
        _model_name = runtime.context.get("supervisor_model", "basic")
        _max_concurrent = runtime.context.get("max_concurrent_research_units", 2)
        _messages = state.get("supervisor_messages", [])
        _research_iterations = state.get("research_iterations", 0)

        # 提示词
        def _assemble_prompt(messages):
            tmp = {
                "max_concurrent_research_units": _max_concurrent,
                "date": get_today_str(),
            }
            return [
                SystemMessage(content=apply_system_prompt_template("supervisor", tmp)),
            ] + messages

        # LLM
        def _get_llm():
            lead_researcher_tools = [ConductResearch, ResearchComplete]
            return get_llm_by_type(_model_name).bind_tools(lead_researcher_tools)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=supervisor | message={response}", "pink"
            )
        )

        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [response],
                "research_iterations": _research_iterations + 1,
            },
        )
    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=supervisor | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=supervisor | error={e}"
            },
        )


# 监督员工具
async def supervisor_tools(
    state: SupervisorState, runtime: Runtime[Context]
) -> Command[Literal["supervisor", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.get("trace_id", "default")
        _max_concurrent = runtime.context.get("max_concurrent_research_units", 2)
        _max_researcher_iterations = runtime.context.get("max_researcher_iterations", 2)
        _supervisor_messages = state.get("supervisor_messages", [])
        _research_iterations = state.get("research_iterations", 0)
        _most_recent_message = _supervisor_messages[-1]

        # 执行
        exceeded_allowed_iterations = _research_iterations >= _max_researcher_iterations
        no_tool_calls = not _most_recent_message.tool_calls  # type: ignore
        research_complete_tool_call = any(
            tool_call["name"] == "ResearchComplete"
            for tool_call in _most_recent_message.tool_calls  # type: ignore
        )

        if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
            return Command(
                goto="__end__",
                update={
                    "notes": get_notes_from_tool_calls(_supervisor_messages),
                    "research_brief": state.get("research_brief", ""),
                },
            )

        all_conduct_research_calls = [
            tool_call
            for tool_call in _most_recent_message.tool_calls  # type: ignore
            if tool_call["name"] == "ConductResearch"
        ]
        conduct_research_calls = all_conduct_research_calls[:_max_concurrent]
        overflow_conduct_research_calls = all_conduct_research_calls[_max_concurrent:]

        coros = []
        for tool_call in conduct_research_calls:
            coros.append(
                ResearcherAgent.ainvoke(
                    {
                        "researcher_messages": [
                            HumanMessage(content=tool_call["args"]["research_topic"]),
                        ],
                    },  # type: ignore
                    context=runtime.context,
                )
            )
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=supervisor_tools | message=use researcher_subgraph: \n tool_call_id: {tool_call['id']}\n tool_args: {tool_call['args']} ",
                    "pink",
                )
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
        raw_notes_concat = "\n".join(
            [
                "\n".join(observation.get("raw_notes", []))
                for observation in tool_results
            ]
        )
        return Command(
            goto="supervisor",
            update={
                "supervisor_messages": tool_messages,
                "raw_notes": [raw_notes_concat],
            },
        )

    except Exception as e:
        logger.error(e)
        return Command(
            goto="__end__",
            update={
                "notes": get_notes_from_tool_calls(_supervisor_messages),
                "research_brief": state.get("research_brief", ""),
            },
        )


# 报告员
async def final_report_generation(
    state: AgentState, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        _model_name = runtime.context.get("report_model", "basic")
        _task_dir = runtime.context.get("task_dir", "./")
        _trace_id = runtime.context.get("trace_id", "default")
        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        notes = state.get("notes", [])
        cleared_state = {
            "notes": {"type": "override", "value": []},
        }

        # 提示词
        def _assemble_prompt(findings):
            tmp = {
                "date": get_today_str(),
                "research_brief": state.get("research_brief", ""),
                "findings": findings,
            }

            return [
                HumanMessage(
                    content=apply_system_prompt_template("final_report_generation", tmp)
                )
            ]

        # LLM
        def _get_llm(model_name):
            return get_llm_by_type(model_name)

        findings = "\n".join(notes)
        max_retries = 3
        current_retry = 0
        while current_retry <= max_retries:
            final_report_prompt = _assemble_prompt(findings)
            try:
                final_report = await _get_llm(_model_name).ainvoke(final_report_prompt)

                await markdown_to_html_tool.ainvoke(
                    {
                        "md_content": final_report.content,
                        "output_file": os.path.join(_work_dir, "final_report.html"),
                    }
                )

                return Command(
                    goto="__end__",
                    update={
                        "final_report": final_report.content,
                        "messages": [final_report],
                        **cleared_state,
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
                "final_report": "Error generating final report: Maximum retries exceeded",
                "messages": [final_report],  # type: ignore
                **cleared_state,
            },
        )

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=final_report_generation | error={e}",
                "red",
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=final_report_generation | error={e}"
            },
        )


#
# Agent - Workflow

# supervisor subgraph
supervisor_builder = StateGraph(SupervisorState, context_schema=Context)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
supervisor_subgraph = supervisor_builder.compile()


# supervisor researcher graph
graph_builder = StateGraph(AgentState, context_schema=Context)
graph_builder.add_node("clarify_with_user", clarify_with_user)
graph_builder.add_node("write_research_brief", write_research_brief)
graph_builder.add_node("research_supervisor", supervisor_subgraph)
graph_builder.add_node("final_report_generation", final_report_generation)
graph_builder.add_edge(START, "clarify_with_user")
graph_builder.add_edge("research_supervisor", "final_report_generation")


graph = graph_builder.compile()
