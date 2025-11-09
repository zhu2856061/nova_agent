# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Annotated, Literal

from langchain_core.messages import (
    HumanMessage,
    MessageLikeRepresentation,
    get_buffer_string,
)
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field

from nova.llms import get_llm_by_type
from nova.prompts.ainovel import apply_system_prompt_template
from nova.tools import read_file_tool, write_file_tool
from nova.utils import (
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
    messages: Annotated[list[MessageLikeRepresentation], add_messages]

    # 用户介入的信息
    user_guidance: str = field(
        default="",
        metadata={"description": "The user guidance to use for the agent."},
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

    architecture_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )


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
# 函数


# 抽取设定
async def extract_setting(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.architecture_model
        _messages = state.messages
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt(messages):
            tmp = {
                "messages": get_buffer_string(messages),
                "user_guidance": _user_guidance,
            }
            return [
                HumanMessage(
                    content=apply_system_prompt_template("extract_setting", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ExtractSetting)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=extract_setting | message={response}",
                "pink",
            )
        )

        _middle_result = {
            "topic": response.topic,  # type: ignore
            "genre": response.genre,  # type: ignore
            "number_of_chapters": response.number_of_chapters,  # type: ignore
            "word_number": response.word_number,  # type: ignore
        }

        _middle_result_txt = json.dumps(_middle_result, ensure_ascii=False)

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_extract_setting.md",
                "text": _middle_result_txt,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=extract_setting | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=extract_setting | error={e}"
            },
        )


# 核心种子
async def core_seed(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.architecture_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt(_extract_setting_result):
            tmp = {
                **_extract_setting_result,
                "user_guidance": _user_guidance,
            }
            print("====>", tmp)
            return [
                HumanMessage(content=apply_system_prompt_template("core_seed", tmp))
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        _extract_setting_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_extract_setting.md",
            }
        )
        _extract_setting_result = json.loads(_extract_setting_result)
        print("====>", _extract_setting_result)

        response = await _get_llm().ainvoke(_assemble_prompt(_extract_setting_result))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=core_seed | message={response}",
                "pink",
            )
        )

        _middle_result = {**_extract_setting_result, "core_seed": response.content}
        _middle_result_txt = json.dumps(_middle_result, ensure_ascii=False)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_core_seed.md",
                "text": _middle_result_txt,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=core_seed | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=core_seed | error={e}"
            },
        )


# 角色动力学
async def character_dynamics(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.architecture_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt(_core_seed_result):
            tmp = {**_core_seed_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("character_dynamics", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        _core_seed_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_core_seed.md",
            }
        )
        _core_seed_result = json.loads(_core_seed_result)

        response = await _get_llm().ainvoke(_assemble_prompt(_core_seed_result))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=character_dynamics | message={response}",
                "pink",
            )
        )

        _middle_result = {**_core_seed_result, "character_dynamics": response.content}
        _middle_result_txt = json.dumps(_middle_result, ensure_ascii=False)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_character_dynamics.md",
                "text": _middle_result_txt,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=character_dynamics | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=character_dynamics | error={e}"
            },
        )


# 世界观
async def world_building(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.architecture_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt(_character_dynamics_result):
            tmp = {**_character_dynamics_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("world_building", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        _character_dynamics_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_character_dynamics.md",
            }
        )
        _character_dynamics_result = json.loads(_character_dynamics_result)

        response = await _get_llm().ainvoke(
            _assemble_prompt(_character_dynamics_result)
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=world_building | message={response}",
                "pink",
            )
        )

        _middle_result = {
            **_character_dynamics_result,
            "world_building": response.content,
        }
        _middle_result_txt = json.dumps(_middle_result, ensure_ascii=False)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_world_building.md",
                "text": _middle_result_txt,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=world_building | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=world_building | error={e}"
            },
        )


# 三幕式情节架构
async def plot_arch(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.architecture_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt(_world_building_result):
            tmp = {**_world_building_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(content=apply_system_prompt_template("plot_arch", tmp))
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        _world_building_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_world_building.md",
            }
        )
        _world_building_result = json.loads(_world_building_result)

        response = await _get_llm().ainvoke(_assemble_prompt(_world_building_result))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=plot_arch | message={response}",
                "pink",
            )
        )

        _middle_result = {**_world_building_result, "plot_arch": response.content}
        _middle_result_txt = json.dumps(_middle_result, ensure_ascii=False)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_plot_arch.md",
                "text": _middle_result_txt,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=plot_arch | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=plot_arch | error={e}"
            },
        )


# 章节目录
async def chapter_blueprint(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.architecture_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_overall_prompt(_novel_architecture, _number_of_chapters):
            tmp = {
                "user_guidance": _user_guidance,
                "novel_architecture": _novel_architecture,
                "number_of_chapters": _number_of_chapters,
            }
            return [
                HumanMessage(
                    content=apply_system_prompt_template("chapter_blueprint", tmp)
                )
            ]

        def _assemble_chunk_prompt(
            _novel_architecture, _number_of_chapters, chapter_list, start, end
        ):
            tmp = {
                "user_guidance": _user_guidance,
                "novel_architecture": _novel_architecture,
                "number_of_chapters": _number_of_chapters,
                "chapter_list": chapter_list,
                "start": start,
                "end": end,
            }
            return [
                HumanMessage(
                    content=apply_system_prompt_template(
                        "chunked_chapter_blueprint", tmp
                    )
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        _plot_arch_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_plot_arch.md",
            }
        )
        _plot_arch_result = json.loads(_plot_arch_result)

        _number_of_chapters = _plot_arch_result["number_of_chapters"]
        _novel_architecture = _plot_arch_result["plot_arch"]

        if _number_of_chapters <= 10:  # 小于10章的一次性产出
            response = await _get_llm().ainvoke(
                _assemble_overall_prompt(_number_of_chapters, _novel_architecture)
            )
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=chapter_blueprint | message={response}",
                    "pink",
                )
            )

            _plot_arch_result = {
                **_plot_arch_result,
                "chapter_blueprint": response.content,
            }
        else:
            current_start = 1
            final_chapter_blueprint = []
            while current_start <= _number_of_chapters:
                current_end = min(current_start + 10, _number_of_chapters)
                chapter_list = "\n\n".join(final_chapter_blueprint[-200:])

                response = await _get_llm().ainvoke(
                    _assemble_chunk_prompt(
                        _number_of_chapters,
                        _novel_architecture,
                        chapter_list,
                        current_start,
                        current_end,
                    )
                )
                final_chapter_blueprint.append(response.content)

                logger.info(
                    set_color(
                        f"trace_id={_trace_id} | node=chunk_chapter_blueprint | current_start={current_start} | current_end={current_end} | message={response}",
                        "pink",
                    )
                )
                current_start = current_end + 1

            _middle_result = {
                **_plot_arch_result,
                "chapter_blueprint": "\n\n".join(final_chapter_blueprint),
            }

        _middle_result_txt = json.dumps(_middle_result, ensure_ascii=False)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_chapter_blueprint.md",
                "text": _middle_result_txt,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=chapter_blueprint | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=chapter_blueprint | error={e}"
            },
        )


# 结果保存
async def summarize_architecture(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        _middle_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_chapter_blueprint.md",
            }
        )
        _middle_result = json.loads(_middle_result)

        final_content = (
            "#=== 0) 小说设定 ===\n"
            f"主题：{_middle_result['topic']},类型：{_middle_result['genre']},篇幅：约{_middle_result['number_of_chapters']}章（每章{_middle_result['word_number']}字）\n\n"
            "#=== 1) 核心种子 ===\n"
            f"{_middle_result['core_seed']}\n\n"
            "#=== 2) 角色动力学 ===\n"
            f"{_middle_result['character_dynamics']}\n\n"
            "#=== 3) 世界观 ===\n"
            f"{_middle_result['world_building']}\n\n"
            "#=== 4) 三幕式情节架构 ===\n"
            f"{_middle_result['plot_arch']}\n"
        )
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_architecture.md",
                "text": final_content,
            }
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=summarize_architecture | message=save to {_work_dir}/novel_architecture.md",
                "pink",
            )
        )

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_chapter_blueprint.md",
                "text": _middle_result["chapter_blueprint"],
            }
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=save_chapter_blueprint | message=save to {_work_dir}/novel_chapter_blueprint.md",
                "pink",
            )
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=summarize_architecture | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=summarize_architecture | error={e}"
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
_summarize_architecture = StateGraph(State, context_schema=Context)
_summarize_architecture.add_node("summarize_architecture", summarize_architecture)
_summarize_architecture.add_edge(START, "summarize_architecture")
summarize_architecture_agent = _summarize_architecture.compile()
