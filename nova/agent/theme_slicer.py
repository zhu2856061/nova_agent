# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from typing import List, Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.agent import Context, Messages, State
from nova.utils.common import convert_base_message, get_today_str
from nova.utils.log_utils import log_info_set_color

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


# ######################################################################################
# 函数
@Agent_Hooks_Instance.node_with_hooks(node_name="theme_slicer")
async def theme_slicer(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["human_feedback", "__end__"]]:
    _NODE_NAME = "theme_slicer"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _messages = (
        state.messages.value if isinstance(state.messages, Messages) else state.messages
    )
    _human_in_loop_value = state.user_guidance.get("human_in_loop_value", "")

    # 提示词
    def _assemble_prompt(messages):
        tmp = {
            "date": get_today_str(),
            "content": get_buffer_string(messages),
            "user_guidance": _human_in_loop_value,
        }

        _prompt_tamplate = Prompts_Provider_Instance.get_template("theme", _NODE_NAME)
        return [
            HumanMessage(
                content=Prompts_Provider_Instance.prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ]

    # 4 大模型
    response = await LLMS_Provider_Instance.llm_wrap_hooks(
        _thread_id,
        _NODE_NAME,
        _assemble_prompt(_messages),
        _model_name,
        structured_output=Topics,
    )

    _data = []
    for topic in response.topics:  # type: ignore
        _data.append(topic.model_dump())

    return Command(
        goto="human_feedback",
        update={
            "code": 0,
            "err_message": "ok",
            "messages": Messages(type="add", value=[AIMessage(content=_data)]),
            "data": {"result": _data},
        },
    )


@Agent_Hooks_Instance.node_with_hooks(node_name="human_feedback")
async def human_feedback(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["theme_slicer", "__end__"]]:
    _NODE_NAME = "human_feedback"

    # 变量
    _thread_id = runtime.context.thread_id
    _messages = (
        state.messages.value if isinstance(state.messages, Messages) else state.messages
    )

    value = interrupt(
        {
            "message_id": _thread_id,
            "content": "对生成的topic进行确定",
        }
    )
    log_info_set_color(_thread_id, _NODE_NAME, value)

    _new_v = []
    for v in _messages:
        if isinstance(v, BaseMessage):
            v = convert_base_message(v)
        _new_v.append(v)

    if value["human_in_loop"] == "确定":
        return Command(goto="__end__")
    else:
        return Command(
            goto="theme_slicer",
            update={
                "user_guidance": {"human_in_loop_value": value["human_in_loop"]},
                "messages": Messages(type="override", value=_new_v),
            },
        )


def compile_theme_slicer_agent():
    # researcher subgraph
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node("theme_slicer", theme_slicer)
    _agent.add_node("human_feedback", human_feedback)
    _agent.add_edge(START, "theme_slicer")

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)
