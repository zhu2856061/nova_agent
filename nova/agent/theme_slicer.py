# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from dataclasses import dataclass, field
from typing import Annotated, List, Literal, Optional

from langchain_core.messages import MessageLikeRepresentation
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova.llms import get_llm_by_type
from nova.prompts.theme_slicer import apply_system_prompt_template
from nova.utils import (
    get_today_str,
    set_color,
)

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量
class Topic(BaseModel):
    id: int = Field(description="The id of the topic")
    title: str = Field(description="The title of the topic")
    description: str = Field(description="The description of the topic")
    keywords: List[str] = Field(description="The keywords of the topic")


# clarify_with_user uses this
class Topics(BaseModel):
    topics: List[Topic] = Field(description="The topics")


@dataclass(kw_only=True)
class State:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    topic: Optional[List[Topic]] = field(
        default=None,
        metadata={"description": "The error message to use for the agent."},
    )
    theme_slicer_messages: Annotated[list[MessageLikeRepresentation], add_messages]


@dataclass(kw_only=True)
class Context:
    trace_id: str = field(
        default="default",
        metadata={"description": "The trace_id to use for the agent."},
    )

    theme_slicer_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )


# ######################################################################################
# 函数
async def theme_slicer(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.theme_slicer_model
        _messages = state.theme_slicer_messages

        # 提示词
        def _assemble_prompt(messages):
            content = apply_system_prompt_template(
                "theme_slicer", {"date": get_today_str()}
            )

            messages[-1].content = content + messages[-1].content

            return messages

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(Topics)

        _tmp_messages = _assemble_prompt(_messages)

        msg = await _get_llm().ainvoke(_tmp_messages)

        return Command(goto="__end__", update={"topic": msg.topics})  # type: ignore

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=theme_slicer | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=theme_slicer | error={e}"
            },
        )


async def human_in_loop(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["theme_slicer", "__end__"]]:
    _trace_id = runtime.context.trace_id
    value = interrupt(
        {
            "message_id": _trace_id,
            "content": "对生成的topic进行确定",
        }
    )
    print("===>", value)
    if value["result"] == "确定":
        return Command(goto="__end__")
    else:
        return Command(goto="theme_slicer")


# researcher subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("theme_slicer", theme_slicer)
_agent.add_node("human_feedback", human_in_loop)
_agent.add_edge(START, "theme_slicer")
_agent.add_edge("theme_slicer", "human_feedback")

checkpointer = InMemorySaver()
theme_slicer_agent = _agent.compile(checkpointer=checkpointer)
