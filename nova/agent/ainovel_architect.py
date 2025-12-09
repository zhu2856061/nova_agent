# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
from typing import Literal

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova import CONF
from nova.llms import get_llm_by_type
from nova.model.agent import Context, Messages, State
from nova.prompts.template import apply_prompt_template, get_prompt
from nova.tools import read_file_tool, write_file_tool
from nova.utils import log_error_set_color, log_info_set_color
from nova.utils.common import convert_base_message

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


# 抽取设定
async def extract_setting(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "extract_setting"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model_name = runtime.context.model
        _config = runtime.context.config
        _user_guidance = state.user_guidance
        _messages = state.messages.value

        prompt_dir = _config.get("prompt_dir")
        result_dir = _config.get("result_dir")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt():
            tmp = {
                "messages": get_buffer_string(_messages) if _messages else "",  # type: ignore
                "user_guidance": _human_in_loop_value,
            }
            _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ExtractSetting)

        response = await _get_llm().ainvoke(_assemble_prompt())
        log_info_set_color(_thread_id, _NODE_NAME, response)

        _result = {
            _NODE_NAME: {
                "topic": response.topic,  # type: ignore
                "genre": response.genre,  # type: ignore
                "number_of_chapters": response.number_of_chapters,  # type: ignore
                "word_number": response.word_number,  # type: ignore
            }
        }

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 核心种子
async def core_seed(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "core_seed"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model_name = runtime.context.model
        _user_guidance = state.user_guidance
        _config = runtime.context.config

        prompt_dir = _config.get("prompt_dir")
        result_dir = _config.get("result_dir")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():
            _extract_setting_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/extract_setting.md",
                }
            )
            _extract_setting_result = json.loads(_extract_setting_result)[
                "extract_setting"
            ]
            tmp = {
                **_extract_setting_result,
                "user_guidance": _human_in_loop_value,
            }
            _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(await _assemble_prompt())
        log_info_set_color(_thread_id, _NODE_NAME, response)

        _result = {_NODE_NAME: response.content}

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 世界观
async def world_building(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "world_building"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model_name = runtime.context.model
        _user_guidance = state.user_guidance
        _config = runtime.context.config

        prompt_dir = _config.get("prompt_dir")
        result_dir = _config.get("result_dir")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():
            # 抽取设置结果
            _extract_setting_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/extract_setting.md",
                }
            )
            _extract_setting_result = json.loads(_extract_setting_result)[
                "extract_setting"
            ]

            # 种子结果
            _core_seed_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/core_seed.md",
                }
            )
            _core_seed_result = json.loads(_core_seed_result)

            # 聚合所有信息
            _extract_setting_result.update(_core_seed_result)

            # 入参
            tmp = {**_extract_setting_result, "user_guidance": _human_in_loop_value}
            _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(await _assemble_prompt())
        log_info_set_color(_thread_id, _NODE_NAME, response)

        _result = {_NODE_NAME: response.content}

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 角色动力学
async def character_dynamics(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "character_dynamics"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model_name = runtime.context.model
        _user_guidance = state.user_guidance
        _config = runtime.context.config

        prompt_dir = _config.get("prompt_dir")
        result_dir = _config.get("result_dir")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():
            # 抽取设置结果
            _extract_setting_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/extract_setting.md",
                }
            )
            _extract_setting_result = json.loads(_extract_setting_result)[
                "extract_setting"
            ]

            # 种子结果
            _core_seed_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/core_seed.md",
                }
            )
            _core_seed_result = json.loads(_core_seed_result)

            # 世界观结果
            _world_building_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/world_building.md",
                }
            )
            _world_building_result = json.loads(_world_building_result)

            # 聚合所有信息
            _extract_setting_result.update(_core_seed_result)
            _extract_setting_result.update(_world_building_result)

            tmp = {**_extract_setting_result, "user_guidance": _human_in_loop_value}
            _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(await _assemble_prompt())
        log_info_set_color(_thread_id, _NODE_NAME, response)

        _result = {_NODE_NAME: response.content}

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 三幕式情节架构
async def plot_arch(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "plot_arch"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model_name = runtime.context.model
        _user_guidance = state.user_guidance
        _config = runtime.context.config

        prompt_dir = _config.get("prompt_dir")
        result_dir = _config.get("result_dir")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():
            # 抽取设置结果
            _extract_setting_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/extract_setting.md",
                }
            )
            _extract_setting_result = json.loads(_extract_setting_result)[
                "extract_setting"
            ]

            # 种子结果
            _core_seed_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/core_seed.md",
                }
            )
            _core_seed_result = json.loads(_core_seed_result)

            # 世界观结果
            _world_building_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/world_building.md",
                }
            )
            _world_building_result = json.loads(_world_building_result)

            # 角色信息
            _character_dynamics_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/character_dynamics.md",
                }
            )
            _character_dynamics_result = json.loads(_character_dynamics_result)

            # 聚合所有信息
            _extract_setting_result.update(_core_seed_result)
            _extract_setting_result.update(_world_building_result)
            _extract_setting_result.update(_character_dynamics_result)

            tmp = {**_extract_setting_result, "user_guidance": _human_in_loop_value}
            _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(await _assemble_prompt())
        log_info_set_color(_thread_id, _NODE_NAME, response)

        _result = {_NODE_NAME: response.content}

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        _result = {_NODE_NAME: response.content}
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 章节目录
async def chapter_blueprint(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "chapter_blueprint"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _model_name = runtime.context.model
        _user_guidance = state.user_guidance
        _config = runtime.context.config

        prompt_dir = _config.get("prompt_dir")
        result_dir = _config.get("result_dir")
        _human_in_loop_value = _user_guidance.get("human_in_loop_value", "")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        _number_of_chapters = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/extract_setting.md",
            }
        )
        _number_of_chapters = json.loads(_number_of_chapters)["extract_setting"][
            "number_of_chapters"
        ]

        # 提示词
        async def _assemble_prompt(chapter_list, start, end):
            # 抽取设置结果
            _extract_setting_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/extract_setting.md",
                }
            )
            _extract_setting_result = json.loads(_extract_setting_result)[
                "extract_setting"
            ]

            # 种子结果
            _core_seed_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/core_seed.md",
                }
            )
            _core_seed_result = json.loads(_core_seed_result)

            # 世界观结果
            _world_building_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/world_building.md",
                }
            )
            _world_building_result = json.loads(_world_building_result)

            # 角色信息
            _character_dynamics_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/character_dynamics.md",
                }
            )
            _character_dynamics_result = json.loads(_character_dynamics_result)

            # 三幕式情节架构
            _plot_arch_result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/plot_arch.md",
                }
            )
            _plot_arch_result = json.loads(_plot_arch_result)

            # 聚合所有信息
            _extract_setting_result.update(_core_seed_result)
            _extract_setting_result.update(_world_building_result)
            _extract_setting_result.update(_character_dynamics_result)
            _extract_setting_result.update(_plot_arch_result)

            tmp = {
                **_extract_setting_result,
                "user_guidance": _human_in_loop_value,
                "chapter_list": chapter_list,
                "start": start,
                "end": end,
            }
            _prompt_tamplate = get_prompt("ainovel", _NODE_NAME, prompt_dir)
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        current_start = 1
        final_chapter_blueprint = []
        while current_start <= _number_of_chapters:
            current_end = min(current_start + 10, _number_of_chapters)
            chapter_list = "\n\n".join(final_chapter_blueprint[-200:])
            response = await _get_llm().ainvoke(
                await _assemble_prompt(chapter_list, current_start, current_end)
            )
            log_info_set_color(_thread_id, _NODE_NAME, response)
            final_chapter_blueprint.append(response.content)

            current_start = current_end + 1

        _result = {_NODE_NAME: "\n\n".join(final_chapter_blueprint)}

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(_result, ensure_ascii=False),
            }
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": _result,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 结果保存
async def build_architecture(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "build_architecture"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
        _config = runtime.context.config

        result_dir = _config.get("result_dir")

        if result_dir:
            _work_dir = result_dir
        else:
            _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 抽取设置结果
        _extract_setting_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/extract_setting.md",
            }
        )

        _extract_setting_result = json.loads(_extract_setting_result)["extract_setting"]

        # 小说设定
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_extract_setting.md",
                "text": json.dumps(_extract_setting_result, ensure_ascii=False),
            }
        )

        # 种子结果
        _core_seed_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/core_seed.md",
            }
        )
        _core_seed_result = json.loads(_core_seed_result)

        # 世界观结果
        _world_building_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/world_building.md",
            }
        )
        _world_building_result = json.loads(_world_building_result)

        # 角色信息
        _character_dynamics_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/character_dynamics.md",
            }
        )
        _character_dynamics_result = json.loads(_character_dynamics_result)

        # 三幕式情节架构
        _plot_arch_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/plot_arch.md",
            }
        )
        _plot_arch_result = json.loads(_plot_arch_result)

        # 聚合所有信息
        _extract_setting_result.update(_core_seed_result)
        _extract_setting_result.update(_world_building_result)
        _extract_setting_result.update(_character_dynamics_result)
        _extract_setting_result.update(_plot_arch_result)

        final_content = (
            "#=== 0) 小说设定 ===\n"
            f"主题：{_extract_setting_result['topic']},类型：{_extract_setting_result['genre']},篇幅：约{_extract_setting_result['number_of_chapters']}章（每章{_extract_setting_result['word_number']}字）\n\n"
            "#=== 1) 核心种子 ===\n"
            f"{_extract_setting_result['core_seed']}\n\n"
            "#=== 2) 角色动力学 ===\n"
            f"{_extract_setting_result['character_dynamics']}\n\n"
            "#=== 3) 世界观 ===\n"
            f"{_extract_setting_result['world_building']}\n\n"
            "#=== 4) 三幕式情节架构 ===\n"
            f"{_extract_setting_result['plot_arch']}\n"
        )
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_architecture.md",
                "text": final_content,
            }
        )
        log_info_set_color(
            _thread_id, _NODE_NAME, f"save to {_work_dir}/novel_architecture.md"
        )

        # 小说章节目录简述
        _chapter_blueprint_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/chapter_blueprint.md",
            }
        )
        _chapter_blueprint_result = json.loads(_chapter_blueprint_result)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_chapter_blueprint.md",
                "text": _chapter_blueprint_result["chapter_blueprint"],
            }
        )
        log_info_set_color(
            _thread_id, _NODE_NAME, f"save to {_work_dir}/novel_chapter_blueprint.md"
        )
        final_content = (
            final_content
            + "\n#=== 3) 世界观 ===\n\n"
            + _chapter_blueprint_result["chapter_blueprint"]
        )
        return {
            "code": 0,
            "err_message": "ok",
            "data": final_content,
            "human_in_loop_node": _NODE_NAME,
        }

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }


# 人工指导
async def human_in_loop_guidance(
    state: State, runtime: Runtime[Context]
) -> Command[
    Literal[
        "core_seed",
        "character_dynamics",
        "world_building",
        "plot_arch",
        "chapter_blueprint",
    ]
]:
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


# 人工确认
async def human_in_loop_agree(
    state: State, runtime: Runtime[Context]
) -> Command[
    Literal[
        "extract_setting",
        "core_seed",
        "character_dynamics",
        "human_in_loop_guidance",
        "world_building",
        "plot_arch",
        "chapter_blueprint",
        "build_architecture",
        "__end__",
    ]
]:
    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF["SYSTEM"]["task_dir"]
    _code = state.code
    _human_in_loop_node = state.human_in_loop_node
    _data = state.data

    _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    if _code != 0:
        return Command(goto="__end__")

    guidance_tip = f"对于`{_human_in_loop_node}`的结果是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`"
    value = interrupt(
        {
            "message_id": _thread_id,
            "content": guidance_tip.format(_human_in_loop_node),
        }
    )

    _current_node = _human_in_loop_node
    if _current_node == "extract_setting":
        _next_node = "core_seed"
    elif _current_node == "core_seed":
        _next_node = "world_building"
    elif _current_node == "world_building":
        _next_node = "character_dynamics"
    elif _current_node == "character_dynamics":
        _next_node = "plot_arch"
    elif _current_node == "plot_arch":
        _next_node = "chapter_blueprint"
    elif _current_node == "chapter_blueprint":
        _next_node = "build_architecture"
    else:
        return Command(
            goto="__end__", update={"code": 1, "err_message": "node not found"}
        )
    _new_v = []
    for v in state.messages.value:
        if isinstance(v, BaseMessage):
            v = convert_base_message(v)
        _new_v.append(v)

    if value["human_in_loop"] == "满意" and _next_node == "build_architecture":
        return Command(goto="build_architecture")

    elif value["human_in_loop"] == "满意":
        return Command(
            goto="human_in_loop_guidance",
            update={
                "messages": Messages(type="override", value=_new_v),
                "human_in_loop_node": _next_node,
            },
        )

    else:
        tmp = json.dumps(_data, ensure_ascii=False)
        tmp = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{value['human_in_loop']}\n\n</用户修改建议>"
        return Command(
            goto=_current_node,  # type: ignore
            update={
                "messages": Messages(type="override", value=_new_v),
                "user_guidance": {"human_in_loop_value": tmp},
            },
        )


# 抽取设定 subgraph
_extract_setting = StateGraph(State, context_schema=Context)
_extract_setting.add_node("extract_setting", extract_setting)
_extract_setting.add_edge(START, "extract_setting")
extract_setting_agent = _extract_setting.compile()


# 核心种子 subgraph
_core_seed = StateGraph(State, context_schema=Context)
_core_seed.add_node("core_seed", core_seed)
_core_seed.add_edge(START, "core_seed")
core_seed_agent = _core_seed.compile()


# 角色动力学 subgraph
_character_dynamics = StateGraph(State, context_schema=Context)
_character_dynamics.add_node("character_dynamics", character_dynamics)
_character_dynamics.add_edge(START, "character_dynamics")
character_dynamics_agent = _character_dynamics.compile()


# 世界观 subgraph
_world_building = StateGraph(State, context_schema=Context)
_world_building.add_node("world_building", world_building)
_world_building.add_edge(START, "world_building")
world_building_agent = _world_building.compile()


# 三幕式情节架构 subgraph
_plot_arch = StateGraph(State, context_schema=Context)
_plot_arch.add_node("plot_arch", plot_arch)
_plot_arch.add_edge(START, "plot_arch")
plot_arch_agent = _plot_arch.compile()


# 章节目录 subgraph
_chapter_blueprint = StateGraph(State, context_schema=Context)
_chapter_blueprint.add_node("chapter_blueprint", chapter_blueprint)
_chapter_blueprint.add_edge(START, "chapter_blueprint")
chapter_blueprint_agent = _chapter_blueprint.compile()

# 组织结果 subgraph
_build_architecture = StateGraph(State, context_schema=Context)
_build_architecture.add_node("build_architecture", build_architecture)
_build_architecture.add_edge(START, "build_architecture")
build_architecture_agent = _build_architecture.compile()

# 全流程 graph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("extract_setting", extract_setting)
_agent.add_node("core_seed", core_seed)
_agent.add_node("character_dynamics", character_dynamics)
_agent.add_node("world_building", world_building)
_agent.add_node("plot_arch", plot_arch)
_agent.add_node("chapter_blueprint", chapter_blueprint)
_agent.add_node("build_architecture", build_architecture)

_agent.add_node("human_in_loop_guidance", human_in_loop_guidance)
_agent.add_node("human_in_loop_agree", human_in_loop_agree)

_agent.add_edge(START, "extract_setting")
_agent.add_edge("extract_setting", "human_in_loop_agree")
_agent.add_edge("core_seed", "human_in_loop_agree")
_agent.add_edge("character_dynamics", "human_in_loop_agree")
_agent.add_edge("world_building", "human_in_loop_agree")
_agent.add_edge("plot_arch", "human_in_loop_agree")
_agent.add_edge("chapter_blueprint", "human_in_loop_agree")
_agent.add_edge("build_architecture", END)

checkpointer = InMemorySaver()
ainovel_architecture_agent = _agent.compile(checkpointer=checkpointer)

# png_bytes = ainovel_architecture_agent.get_graph(xray=True).draw_mermaid()
# logger.info(f"ainovel_architecture_agent: \n\n{png_bytes}")
