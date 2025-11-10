# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
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
    code: int = field(
        default=0,
        metadata={"description": "The code to use for the agent."},
    )
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
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

    novel_model: str = field(
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
async def extract_setting(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt():
            tmp = {
                "messages": _user_guidance,
                "user_guidance": "",
            }

            return [
                HumanMessage(
                    content=apply_system_prompt_template("extract_setting", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ExtractSetting)

        response = await _get_llm().ainvoke(_assemble_prompt())
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

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=extract_setting | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


# 核心种子
async def core_seed(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt(_extract_setting_result):
            tmp = {
                **_extract_setting_result,
                "user_guidance": _user_guidance,
            }
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

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=core_seed | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


# 角色动力学
async def character_dynamics(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
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

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=character_dynamics | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


# 世界观
async def world_building(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
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

        return {"code": 0, "err_message": "ok"}
    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=world_building | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


# 三幕式情节架构
async def plot_arch(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
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

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=plot_arch | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


# 章节目录
async def chapter_blueprint(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_overall_prompt(_plot_arch_result):
            tmp = {**_plot_arch_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("chapter_blueprint", tmp)
                )
            ]

        def _assemble_chunk_prompt(_plot_arch_result, chapter_list, start, end):
            tmp = {
                **_plot_arch_result,
                "user_guidance": _user_guidance,
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

        if _number_of_chapters <= 10:  # 小于10章的一次性产出
            response = await _get_llm().ainvoke(
                _assemble_overall_prompt(_plot_arch_result)
            )
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=chapter_blueprint | message={response}",
                    "pink",
                )
            )

            _middle_result = {
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
                        _plot_arch_result,
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
                "file_path": f"{_work_dir}/novel_blueprint.md",
                "text": _middle_result_txt,
            }
        )

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=chapter_blueprint | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


# 结果保存
async def summarize_architecture(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        _middle_result = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_blueprint.md",
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

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=summarize_architecture | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


def parse_chapter_blueprint(blueprint_text: str):
    """
    解析整份章节蓝图文本，返回一个列表，每个元素是一个 dict：
    {
      "chapter_number": int,
      "chapter_title": str,
      "chapter_role": str,       # 本章定位
      "chapter_purpose": str,    # 核心作用
      "suspense_level": str,     # 悬念密度
      "foreshadowing": str,      # 伏笔操作
      "plot_twist_level": str,   # 认知颠覆
      "chapter_summary": str     # 本章简述
    }
    """

    # 先按空行进行分块，以免多章之间混淆
    chunks = re.split(r"\n\s*\n", blueprint_text.strip())
    results = []

    # 兼容是否使用方括号包裹章节标题
    # 例如：
    #   第1章 - 紫极光下的预兆
    # 或
    #   第1章 - [紫极光下的预兆]
    chapter_number_pattern = re.compile(r"^第\s*(\d+)\s*章\s*-\s*\[?(.*?)\]?$")

    role_pattern = re.compile(r"^本章定位：\s*\[?(.*)\]?$")
    purpose_pattern = re.compile(r"^核心作用：\s*\[?(.*)\]?$")
    suspense_pattern = re.compile(r"^悬念密度：\s*\[?(.*)\]?$")
    foreshadow_pattern = re.compile(r"^伏笔操作：\s*\[?(.*)\]?$")
    twist_pattern = re.compile(r"^认知颠覆：\s*\[?(.*)\]?$")
    summary_pattern = re.compile(r"^本章简述：\s*\[?(.*)\]?$")

    for chunk in chunks:
        lines = chunk.strip().splitlines()
        if not lines:
            continue

        chapter_number = None
        chapter_title = ""
        chapter_role = ""
        chapter_purpose = ""
        suspense_level = ""
        foreshadowing = ""
        plot_twist_level = ""
        chapter_summary = ""

        # 先匹配第一行（或前几行），找到章号和标题
        header_match = chapter_number_pattern.match(lines[0].strip())
        if not header_match:
            # 不符合“第X章 - 标题”的格式，跳过
            continue

        chapter_number = int(header_match.group(1))
        chapter_title = header_match.group(2).strip()

        # 从后面的行匹配其他字段
        for line in lines[1:]:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            m_role = role_pattern.match(line_stripped)
            if m_role:
                chapter_role = m_role.group(1).strip()
                continue

            m_purpose = purpose_pattern.match(line_stripped)
            if m_purpose:
                chapter_purpose = m_purpose.group(1).strip()
                continue

            m_suspense = suspense_pattern.match(line_stripped)
            if m_suspense:
                suspense_level = m_suspense.group(1).strip()
                continue

            m_foreshadow = foreshadow_pattern.match(line_stripped)
            if m_foreshadow:
                foreshadowing = m_foreshadow.group(1).strip()
                continue

            m_twist = twist_pattern.match(line_stripped)
            if m_twist:
                plot_twist_level = m_twist.group(1).strip()
                continue

            m_summary = summary_pattern.match(line_stripped)
            if m_summary:
                chapter_summary = m_summary.group(1).strip()
                continue

        results.append(
            {
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "chapter_role": chapter_role,
                "chapter_purpose": chapter_purpose,
                "suspense_level": suspense_level,
                "foreshadowing": foreshadowing,
                "plot_twist_level": plot_twist_level,
                "chapter_summary": chapter_summary,
            }
        )

    # 按照 chapter_number 排序后返回
    results.sort(key=lambda x: x["chapter_number"])
    return results


def get_chapter_info_from_blueprint(blueprint_text: str, target_chapter_number: int):
    """
    在已经加载好的章节蓝图文本中，找到对应章号的结构化信息，返回一个 dict。
    若找不到则返回一个默认的结构。
    """
    all_chapters = parse_chapter_blueprint(blueprint_text)
    for ch in all_chapters:
        if ch["chapter_number"] == target_chapter_number:
            return ch
    # 默认返回
    return {
        "chapter_number": target_chapter_number,
        "chapter_title": f"第{target_chapter_number}章",
        "chapter_role": "",
        "chapter_purpose": "",
        "suspense_level": "",
        "foreshadowing": "",
        "plot_twist_level": "",
        "chapter_summary": "",
    }


def get_last_n_chapters_text(work_dir: str, current_chapter_num: int, n: int = 3):
    """
    从目录 chapters_dir 中获取最近 n 章的文本内容，返回文本列表。
    """
    texts = []
    start_chap = max(1, current_chapter_num - n)
    for c in range(start_chap, current_chapter_num):
        if os.path.exists(f"{work_dir}/chapter_{c}/第{c}章.md"):
            chap_text = read_file_tool.run(
                {"file_path": f"{work_dir}/chapter_{c}/第{c}章.md"}
            )
            texts.append(chap_text)
        else:
            texts.append("")
    return texts


# 章节内容
async def chapter_draft(state: State, runtime: Runtime[Context]):
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _model_name = runtime.context.novel_model
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        if os.path.exists(f"{_work_dir}/novel_extract_setting.md"):
            _novel_setting = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_extract_setting.md"}
            )
            _novel_setting = json.loads(_novel_setting)
            _word_number = _novel_setting["word_number"]
        else:
            err_message = f"trace_id={_trace_id} | node=chapter_draft | error=novel_setting is None"
            logger.error(set_color(err_message, "red"))
            return {"code": 1, "err_message": err_message}
        #
        if os.path.exists(f"{_work_dir}/novel_architecture.md"):
            _novel_architecture = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_architecture.md"}
            )
        else:
            err_message = f"trace_id={_trace_id} | node=chapter_draft | error=novel_architecture is None"
            logger.error(set_color(err_message, "red"))
            return {"code": 1, "err_message": err_message}
        if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
            _novel_chapter_blueprint = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
            )
        else:
            err_message = f"trace_id={_trace_id} | node=chapter_draft | error=novel_chapter_blueprint is None"
            logger.error(set_color(err_message, "red"))
            return {"code": 1, "err_message": err_message}

        # 提示词
        def _assemble_prompt(
            target,
            current_chapter_id=1,
            previous_chapter_text="",
            previous_global_summary="",
            previous_character_state="",
            new_global_summary="",
            new_character_state="",
            summarize_recent_chapters="",
            combined_text="",
            chapter_info={},
            next_chapter_info={},
            characters_involved="",
            key_items="",
            scene_location="",
            time_constraint="",
        ):
            if target == "global_summary":
                tmp = {
                    "previous_chapter_text": previous_chapter_text,
                    "previous_global_summary": previous_global_summary,
                }
                return [
                    HumanMessage(
                        content=apply_system_prompt_template("global_summary", tmp)
                    )
                ]

            elif target == "update_character_state":
                tmp = {
                    "previous_chapter_text": previous_chapter_text,
                    "previous_character_state": previous_character_state,
                }
                return [
                    HumanMessage(
                        content=apply_system_prompt_template(
                            "update_character_state", tmp
                        )
                    )
                ]

            elif target == "summarize_recent_chapters":
                tmp = {
                    "combined_text": combined_text,
                    "novel_number": current_chapter_id,
                    "chapter_title": chapter_info.get("chapter_title", "未命名"),
                    "chapter_role": chapter_info.get("chapter_role", "常规章节"),
                    "chapter_purpose": chapter_info.get("chapter_purpose", "内容推进"),
                    "suspense_level": chapter_info.get("suspense_level", "中等"),
                    "foreshadowing": chapter_info.get("foreshadowing", "无"),
                    "plot_twist_level": chapter_info.get("plot_twist_level", "★☆☆☆☆"),
                    "chapter_summary": chapter_info.get("chapter_summary", ""),
                    "next_chapter_number": current_chapter_id + 1,
                    "next_chapter_title": next_chapter_info.get(
                        "chapter_title", "（未命名）"
                    ),
                    "next_chapter_role": next_chapter_info.get(
                        "chapter_role", "过渡章节"
                    ),
                    "next_chapter_purpose": next_chapter_info.get(
                        "chapter_purpose", "承上启下"
                    ),
                    "next_chapter_summary": next_chapter_info.get(
                        "chapter_summary", "衔接过渡内容"
                    ),
                    "next_chapter_suspense_level": next_chapter_info.get(
                        "suspense_level", "中等"
                    ),
                    "next_chapter_foreshadowing": next_chapter_info.get(
                        "foreshadowing", "无特殊伏笔"
                    ),
                    "next_chapter_plot_twist_level": next_chapter_info.get(
                        "plot_twist_level", "★☆☆☆☆"
                    ),
                }
                return [
                    HumanMessage(
                        content=apply_system_prompt_template(
                            "summarize_recent_chapters", tmp
                        )
                    )
                ]

            elif target == "create_character_state":
                tmp = {
                    "novel_architecture": _novel_architecture,
                }
                return [
                    HumanMessage(
                        content=apply_system_prompt_template(
                            "create_character_state", tmp
                        )
                    )
                ]

            elif target == "first_chapter_draft":
                chapter_title = chapter_info["chapter_title"]
                chapter_role = chapter_info["chapter_role"]
                chapter_purpose = chapter_info["chapter_purpose"]
                suspense_level = chapter_info["suspense_level"]
                foreshadowing = chapter_info["foreshadowing"]
                plot_twist_level = chapter_info["plot_twist_level"]
                chapter_summary = chapter_info["chapter_summary"]

                tmp = {
                    "novel_number": current_chapter_id,
                    "word_number": _word_number,
                    "chapter_title": chapter_title,
                    "chapter_role": chapter_role,
                    "chapter_purpose": chapter_purpose,
                    "suspense_level": suspense_level,
                    "foreshadowing": foreshadowing,
                    "plot_twist_level": plot_twist_level,
                    "chapter_summary": chapter_summary,
                    "characters_involved": characters_involved,
                    "key_items": key_items,
                    "scene_location": scene_location,
                    "time_constraint": time_constraint,
                    "user_guidance": _user_guidance,
                    "novel_architecture": _novel_architecture,
                    "character_state": new_character_state,
                }

                return [
                    HumanMessage(
                        content=apply_system_prompt_template("first_chapter_draft", tmp)
                    )
                ]

            elif target == "next_chapter_draft":
                chapter_title = chapter_info["chapter_title"]
                chapter_role = chapter_info["chapter_role"]
                chapter_purpose = chapter_info["chapter_purpose"]
                suspense_level = chapter_info["suspense_level"]
                foreshadowing = chapter_info["foreshadowing"]
                plot_twist_level = chapter_info["plot_twist_level"]
                chapter_summary = chapter_info["chapter_summary"]

                next_chapter_title = next_chapter_info.get(
                    "chapter_title", "（未命名）"
                )
                next_chapter_role = next_chapter_info.get("chapter_role", "过渡章节")
                next_chapter_purpose = next_chapter_info.get(
                    "chapter_purpose", "承上启下"
                )
                next_suspense_level = next_chapter_info.get("suspense_level", "中等")
                next_foreshadowing = next_chapter_info.get(
                    "foreshadowing", "无特殊伏笔"
                )
                next_plot_twist_level = next_chapter_info.get(
                    "plot_twist_level", "★☆☆☆☆"
                )
                next_chapter_summary = next_chapter_info.get(
                    "chapter_summary", "衔接过渡内容"
                )

                # (TODO：未来加入知识库，对章节进行筛选)
                filtered_context = ""

                tmp = {
                    "global_summary": new_global_summary,
                    "character_state": new_character_state,
                    "short_summary": summarize_recent_chapters,
                    "previous_chapter_excerpt": combined_text,
                    "novel_number": current_chapter_id,
                    "chapter_title": chapter_title,
                    "chapter_role": chapter_role,
                    "chapter_purpose": chapter_purpose,
                    "suspense_level": suspense_level,
                    "foreshadowing": foreshadowing,
                    "plot_twist_level": plot_twist_level,
                    "chapter_summary": chapter_summary,
                    "next_chapter_number": current_chapter_id + 1,
                    "next_chapter_title": next_chapter_title,
                    "next_chapter_role": next_chapter_role,
                    "next_chapter_purpose": next_chapter_purpose,
                    "next_chapter_suspense_level": next_suspense_level,
                    "next_chapter_foreshadowing": next_foreshadowing,
                    "next_chapter_plot_twist_level": next_plot_twist_level,
                    "next_chapter_summary": next_chapter_summary,
                    "filtered_context": filtered_context,
                    "word_number": _word_number,
                    "characters_involved": characters_involved,
                    "key_items": key_items,
                    "scene_location": scene_location,
                    "time_constraint": time_constraint,
                    "user_guidance": _user_guidance,
                }

                return [
                    HumanMessage(
                        content=apply_system_prompt_template("next_chapter_draft", tmp)
                    )
                ]

            else:
                return [HumanMessage(content="")]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        # 确定当前属于第几章
        dir_path = Path(f"{_work_dir}")
        file_count = sum(1 for item in dir_path.iterdir() if item.is_dir())
        _current_chapter_id = file_count + 1
        os.makedirs(f"{_work_dir}/chapter_{_current_chapter_id}", exist_ok=True)

        # 获取历史信息
        _previous_chapter_text = ""
        _previous_global_summary = ""
        _previous_character_state = ""

        _new_global_summary = ""
        _new_character_state = ""
        _summarize_recent_chapters = ""

        if os.path.exists(f"{_work_dir}/chapter_{_current_chapter_id - 1}"):
            if os.path.exists(
                f"{_work_dir}/chapter_{_current_chapter_id - 1}/第{_current_chapter_id - 1}章.md"
            ):
                _previous_chapter_text = await read_file_tool.arun(
                    {
                        "file_path": f"{_work_dir}/chapter_{_current_chapter_id - 1}/第{_current_chapter_id - 1}章.md"
                    }
                )
            if os.path.exists(
                f"{_work_dir}/chapter_{_current_chapter_id - 1}/global_summary.md"
            ):
                _previous_global_summary = await read_file_tool.arun(
                    {
                        "file_path": f"{_work_dir}/chapter_{_current_chapter_id - 1}/global_summary.md"
                    }
                )

            if os.path.exists(
                f"{_work_dir}/chapter_{_current_chapter_id - 1}/character_state.md"
            ):
                _previous_character_state = await read_file_tool.arun(
                    {
                        "file_path": f"{_work_dir}/chapter_{_current_chapter_id - 1}/character_state.md"
                    }
                )

        # 获取章节概要信息
        _chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id
        )
        # 获取下一章节概要信息
        _next_chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id + 1
        )
        # 获取前文内容和摘要
        _recent_texts = get_last_n_chapters_text(_work_dir, _current_chapter_id, n=3)
        _combined_text = "\n".join(_recent_texts).strip()
        max_combined_length = 4000
        if len(_combined_text) > max_combined_length:
            _combined_text = _combined_text[-max_combined_length:]

        if _previous_chapter_text:
            _new_global_summary = await _get_llm().ainvoke(
                _assemble_prompt(
                    target="global_summary",
                    current_chapter_id=_current_chapter_id,
                    previous_chapter_text=_previous_chapter_text,
                    previous_global_summary=_previous_global_summary,
                )
            )
            _new_global_summary = _new_global_summary.content
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=chapter_draft | message={_new_global_summary}",
                    "pink",
                )
            )
            await write_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/chapter_{_current_chapter_id}/global_summary.md",
                    "text": _new_global_summary,
                }
            )

        if _current_chapter_id == 1:
            _new_character_state = await _get_llm().ainvoke(
                _assemble_prompt("create_character_state")
            )
            _new_character_state = _new_character_state.content
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=chapter_draft | message={_new_character_state}",
                    "pink",
                )
            )
            await write_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/chapter_{_current_chapter_id}/character_state.md",
                    "text": _new_character_state,
                }
            )
        else:
            if _previous_chapter_text and _previous_character_state:
                _new_character_state = await _get_llm().ainvoke(
                    _assemble_prompt(
                        target="update_character_state",
                        current_chapter_id=_current_chapter_id,
                        previous_chapter_text=_previous_chapter_text,
                        previous_character_state=_previous_character_state,
                    )
                )
                _new_character_state = _new_character_state.content
                logger.info(
                    set_color(
                        f"trace_id={_trace_id} | node=chapter_draft | message={_new_character_state}",
                        "pink",
                    )
                )
                await write_file_tool.arun(
                    {
                        "file_path": f"{_work_dir}/chapter_{_current_chapter_id}/character_state.md",
                        "text": _new_character_state,
                    }
                )

        if _combined_text:
            _summarize_recent_chapters = await _get_llm().ainvoke(
                _assemble_prompt(
                    target="summarize_recent_chapters",
                    current_chapter_id=_current_chapter_id,
                    combined_text=_combined_text,
                    chapter_info=_chapter_info,
                    next_chapter_info=_next_chapter_info,
                )
            )
            _summarize_recent_chapters = _summarize_recent_chapters.content
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=chapter_draft | message={_summarize_recent_chapters}",
                    "pink",
                )
            )
            await write_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/chapter_{_current_chapter_id}/summarize_recent_chapters.md",
                    "text": _summarize_recent_chapters,
                }
            )

        if not _new_character_state:
            err_message = f"trace_id={_trace_id} | node=chapter_draft | error=new_character_state: is None"
            logger.error(set_color(err_message, "red"))
            return {"code": 1, "err_message": err_message}

        if _current_chapter_id == 1:
            response = await _get_llm().ainvoke(
                _assemble_prompt(
                    target="first_chapter_draft",
                    current_chapter_id=_current_chapter_id,
                    chapter_info=_chapter_info,
                )
            )
        else:
            response = await _get_llm().ainvoke(
                _assemble_prompt(
                    target="next_chapter_draft",
                    chapter_info=_chapter_info,
                    next_chapter_info=_next_chapter_info,
                    new_global_summary=str(_new_global_summary),
                    new_character_state=str(_new_character_state),
                    summarize_recent_chapters=str(_summarize_recent_chapters),
                )
            )

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter_{_current_chapter_id}/第{_current_chapter_id}章.md",
                "text": f"## 第{_current_chapter_id}章 {_chapter_info['chapter_title']}\n\n{response.content}",
            }
        )

        return {"code": 0, "err_message": "ok"}

    except Exception as e:
        err_message = f"trace_id={_trace_id} | node=chapter_draft | error={e}"
        logger.error(set_color(err_message, "red"))
        return {"code": 1, "err_message": err_message}


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


# 详细章节 subgraph
_chapter_draft = StateGraph(State, context_schema=Context)
_chapter_draft.add_node("chapter_draft", chapter_draft)
_chapter_draft.add_edge(START, "chapter_draft")
chapter_draft_agent = _chapter_draft.compile()
