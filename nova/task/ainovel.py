# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from dataclasses import dataclass, field
from typing import Annotated, Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    MessageLikeRepresentation,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field

from nova.agent.ainovel_architect import ainovel_architecture_agent
from nova.agent.ainovel_chapter import ainovel_chapter_agent
from nova.agent.ainovel_chapter_draft import ainovel_chapter_draft_agent
from nova.llms import get_llm_by_type
from nova.prompts.ainovel import apply_system_prompt_template
from nova.utils import (
    override_reducer,
    set_color,
)

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


@dataclass(kw_only=True)
class AgentState:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    messages: Annotated[list[MessageLikeRepresentation], add_messages]
    architecture_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    number_of_chapters: int = field(
        default=0,
        metadata={"description": "The number of chapters in the novel."},
    )
    word_number: int = field(
        default=0,
        metadata={"description": "The word number of each chapter in the novel."},
    )


@dataclass(kw_only=True)
class Context:
    trace_id: str = field(
        default="default",
        metadata={"description": "The trace_id to use for the agent."},
    )
    task_dir: str = field(
        default="merlin",
        metadata={"description": "The task directory to use for the agent."},
    )
    clarify_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )
    architecture_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )
    chapter_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )
    chunk_size: int = field(
        default=5,
        metadata={"description": "The chunk size to use for the agent."},
    )
    max_chapter_length: int = field(
        default=10,
        metadata={"description": "The max chapter length to use for the agent."},
    )


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


# ######################################################################################
# 函数


# 用户澄清
async def clarify_with_user(
    state: AgentState, runtime: Runtime[Context]
) -> Command[Literal["architecture", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.clarify_model
        _messages = state.messages

        # 提示词
        def _assemble_prompt(messages):
            tmp = {"messages": get_buffer_string(messages)}
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
                update={
                    "messages": [AIMessage(content=response.question)]  # type: ignore
                },
            )
        else:
            return Command(
                goto="architecture",
                update={
                    "architecture_messages": [
                        HumanMessage(content=response.verification)  # type: ignore
                    ]
                },
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


# supervisor researcher graph
graph_builder = StateGraph(AgentState, context_schema=Context)
graph_builder.add_node("clarify_with_user", clarify_with_user)
graph_builder.add_node("architecture", ainovel_architecture_agent)
graph_builder.add_node("chapter", ainovel_chapter_agent)
graph_builder.add_node("chapter_draft", ainovel_chapter_draft_agent)
graph_builder.add_edge(START, "clarify_with_user")
graph_builder.add_edge("architecture", "chapter")
graph_builder.add_edge("chapter", "chapter_draft")
checkpointer = InMemorySaver()
ainovel = graph_builder.compile(checkpointer=checkpointer)
