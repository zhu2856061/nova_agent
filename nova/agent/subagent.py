# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os

from langchain_core.messages import (
    BaseMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova import CONF
from nova.llms import get_llm_by_type
from nova.model.agent import Context, Messages, State
from nova.llms.template import apply_prompt_template, get_prompt
from nova.tools.file_manager import read_file_tool, write_file_tool
from nova.utils.common import convert_base_message
from nova.utils.log_utils import log_error_set_color, log_info_set_color

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


# extract_setting uses this
class ExtractSetting(BaseModel):
    topic: str = Field(
        description="the topic of novel",
    )
    genre: str = Field(
        description="the genre of novel",
    )
    number_of_chapters: int = Field(
        description="the number of chapters in a novel",
    )
    word_number: int = Field(
        description="the word count of each chapter in the novel",
    )


# ######################################################################################


async def create_subagent(
    name,
    *,
    state: State,
    runtime: Runtime[Context],
    assemble_prompt,
    tools,
    with_structured_output,
):
    try:
        # context 信息
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model = runtime.context.model
        _config = runtime.context.config

        # state 信息
        _code = state.code
        _err_message = state.err_message
        _user_guidance = state.user_guidance
        result_dir = _config.get("result_dir")

        _messages = state.messages
        _data = state.data
        _human_in_loop_node = state.user_guidance.get("human_in_loop_node", "")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        # def _assemble_prompt():
        #     tmp = {
        #         "messages": get_buffer_string(_messages) if _messages else "",  # type: ignore
        #         "user_guidance": _human_in_loop_value,
        #     }
        #     _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
        #     return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            if with_structured_output:
                return get_llm_by_type(_model).with_structured_output(
                    with_structured_output
                )
            else:
                return get_llm_by_type(_model)

        response = await _get_llm().ainvoke(assemble_prompt())
        log_info_set_color(_thread_id, name, response)

        if isinstance(response, BaseMessage):
            _result = {name: response.content}
        elif isinstance(response, BaseModel):
            _result = {name: response.model_dump()}
        else:
            _result = {name: response}

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{name}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": name,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, name, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 人工指导
async def human_in_loop_guidance(state: State, runtime: Runtime[Context]):
    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
    _human_in_loop_node = state.human_in_loop_node

    _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    guidance_tip = f"基于上述生成信息准备开始`{_human_in_loop_node}`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`"
    value = interrupt({"message_id": _thread_id, "content": guidance_tip})

    _new_v = []
    for v in state.messages.value:
        if isinstance(v, BaseMessage):
            v = convert_base_message(v)
        _new_v.append(v)

    return Command(
        goto=_human_in_loop_node,  # type: ignore
        update={
            "user_guidance": {"human_in_loop_value": value["human_in_loop"]},
            "messages": Messages(type="override", value=_new_v),
        },
    )


# 抽取设定 subgraph
_extract_setting = StateGraph(State, context_schema=Context)

checkpointer = InMemorySaver()
extract_setting_agent = _extract_setting.compile(checkpointer=checkpointer)


# png_bytes = ainovel_architecture_agent.get_graph(xray=True).draw_mermaid()
# logger.info(f"ainovel_architecture_agent: \n\n{png_bytes}")
