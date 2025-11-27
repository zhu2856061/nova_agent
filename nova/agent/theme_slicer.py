# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova.llms import get_llm_by_type
from nova.model.agent import Context, State
from nova.prompts.template import apply_prompt_template, get_prompt
from nova.utils import get_today_str, log_error_set_color, log_info_set_color

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
async def theme_slicer(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "theme_slicer"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _model_name = runtime.context.model
        _messages = state.messages
        _human_in_loop_node = state.human_in_loop_node

        # 提示词
        def _assemble_prompt(messages):
            tmp = {
                "date": get_today_str(),
                "content": get_buffer_string(messages),
                "user_guidance": _human_in_loop_node,
            }

            _prompt_tamplate = get_prompt("theme", _NODE_NAME)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(Topics)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        log_info_set_color(_thread_id, _NODE_NAME, response)

        _data = []
        for topic in response.topics:  # type: ignore
            _data.append(topic.model_dump())
        return {
            "code": 0,
            "err_message": "ok",
            "messages": AIMessage(content=_data),
            "data": {_NODE_NAME: _data},
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {"code": 1, "err_message": _err_message}


async def human_in_loop(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "human_in_loop"

    # 变量
    _thread_id = runtime.context.thread_id
    _code = state.code
    if _code != 0:
        return Command(goto="__end__")

    value = interrupt(
        {
            "message_id": _thread_id,
            "content": "对生成的topic进行确定",
        }
    )
    log_info_set_color(_thread_id, _NODE_NAME, value)

    if value["human_in_loop"] == "确定":
        return Command(goto="__end__")
    else:
        return Command(
            goto="theme_slicer", update={"human_in_loop_node": value["human_in_loop"]}
        )
    # except Exception as e:
    #     _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
    #     return {"code": 1, "err_message": _err_message}


# researcher subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("theme_slicer", theme_slicer)
_agent.add_node("human_feedback", human_in_loop)
_agent.add_edge(START, "theme_slicer")
_agent.add_edge("theme_slicer", "human_feedback")

checkpointer = InMemorySaver()
theme_slicer_agent = _agent.compile(checkpointer=checkpointer)
