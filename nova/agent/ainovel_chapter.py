# -*- coding: utf-8 -*-
# @Time   : 2025/11/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
import re
from pathlib import Path
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from nova import CONF
from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.agent import Context, Messages, State
from nova.tools import read_file_tool, write_file_tool
from nova.utils.common import convert_base_message
from nova.utils.log_utils import log_error_set_color, log_info_set_color

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


# ######################################################################################
# 函数


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
        if os.path.exists(f"{work_dir}/chapter/chapter_{c}/chapter_draft.md"):
            chap_text = read_file_tool.run(
                {"file_path": f"{work_dir}/chapter_{c}/chapter_draft.md"}
            )
            texts.append(chap_text)
        else:
            texts.append("")
    return texts


# 全局摘要
@Agent_Hooks_Instance.node_with_hooks(node_name="global_summary")
async def global_summary(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "global_summary"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
    _model_name = runtime.context.model
    _user_guidance = state.user_guidance
    _config = runtime.context.config

    prompt_dir = _config.get("prompt_dir")
    result_dir = _config.get("result_dir")

    if result_dir:
        _work_dir = result_dir
    else:
        _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 获得当前章节
    _current_chapter_id = _user_guidance.get("current_chapter_id")
    if not _current_chapter_id:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "current_chapter_id not found"
        )
        return {"code": 1, "err_message": _err_message}
    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    _previous_chapter_text = ""
    _previous_global_summary = ""
    if os.path.exists(f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}"):
        if os.path.exists(
            f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}/chapter_draft.md"
        ):
            _previous_chapter_text = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}/chapter_draft.md"
                }
            )
        if os.path.exists(
            f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}/{_NODE_NAME}.md"
        ):
            _previous_global_summary = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}/{_NODE_NAME}.md"
                }
            )

    if _current_chapter_id > 1 and _previous_chapter_text == "":
        return {
            "code": 1,
            "err_message": f"current_chapter_id={_current_chapter_id}, previous chapter text  not found",
            "messages": Messages(type="end"),
        }
    if _current_chapter_id > 2 and _previous_global_summary == "":
        return {
            "code": 1,
            "err_message": f"current_chapter_id={_current_chapter_id}, previous global summary not found",
            "messages": Messages(type="end"),
        }

    # 提示词
    def _assemble_prompt():
        tmp = {
            "previous_chapter_text": _previous_chapter_text,
            "previous_global_summary": _previous_global_summary,
        }
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "ainovel", _NODE_NAME, prompt_dir
        )
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
        _assemble_prompt(),
        _model_name,
    )

    _result = {_NODE_NAME: response.content}

    await write_file_tool.arun(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/{_NODE_NAME}.md",
            "text": json.dumps(_result, ensure_ascii=False),
        }
    )
    return {"code": 0, "err_message": "ok", "data": _result}


# 创建角色状态
@Agent_Hooks_Instance.node_with_hooks(node_name="create_character_state")
async def create_character_state(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "create_character_state"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
    _model_name = runtime.context.model
    _user_guidance = state.user_guidance
    _config = runtime.context.config

    prompt_dir = _config.get("prompt_dir")
    result_dir = _config.get("result_dir")

    if result_dir:
        _work_dir = result_dir
    else:
        _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 获得当前章节
    _current_chapter_id = _user_guidance.get("current_chapter_id")
    if not _current_chapter_id:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "current_chapter_id not found"
        )
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }
    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    # 获得大纲
    if os.path.exists(f"{_work_dir}/novel_architecture.md"):
        _novel_architecture = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_architecture.md"}
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_architecture not found"
        )
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }

    # 提示词
    def _assemble_prompt():
        tmp = {"novel_architecture": _novel_architecture}
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "ainovel", _NODE_NAME, prompt_dir
        )
        return [
            HumanMessage(
                content=Prompts_Provider_Instance.prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ]

    response = await LLMS_Provider_Instance.llm_wrap_hooks(
        _thread_id,
        _NODE_NAME,
        _assemble_prompt(),
        _model_name,
    )
    _result = {"character_state": response.content}
    await write_file_tool.arun(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/character_state.md",
            "text": json.dumps(_result, ensure_ascii=False),
        }
    )
    return {"code": 0, "err_message": "ok", "data": _result}


# 更新角色状态
@Agent_Hooks_Instance.node_with_hooks(node_name="update_character_state")
async def update_character_state(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "update_character_state"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
    _model_name = runtime.context.model
    _user_guidance = state.user_guidance
    _config = runtime.context.config

    prompt_dir = _config.get("prompt_dir")
    result_dir = _config.get("result_dir")

    if result_dir:
        _work_dir = result_dir
    else:
        _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 获得当前章节
    _current_chapter_id = _user_guidance.get("current_chapter_id")
    if not _current_chapter_id:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "current_chapter_id not found"
        )
        return {"code": 1, "err_message": _err_message}
    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    _previous_chapter_text = read_file_tool.run(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}/chapter_draft.md"
        }
    )

    _previous_character_state = read_file_tool.run(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id - 1}/character_state.md"
        }
    )
    if _previous_chapter_text == "" or _previous_character_state == "":
        return {
            "code": 1,
            "err_message": f"current_chapter_id={_current_chapter_id}, previous chapter text or previous_character_state not found",
            "messages": Messages(type="end"),
        }

    # 提示词
    def _assemble_prompt():
        tmp = {
            "previous_chapter_text": _previous_chapter_text,
            "previous_character_state": _previous_character_state,
        }
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "ainovel", _NODE_NAME, prompt_dir
        )
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
        _assemble_prompt(),
        _model_name,
    )

    _result = {"character_state": response.content}

    await write_file_tool.arun(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/character_state.md",
            "text": json.dumps(_result, ensure_ascii=False),
        }
    )
    return {"code": 0, "err_message": "ok", "data": _result}


# 最近3章节，当前章节，下一章节，构建当前章节的摘要
@Agent_Hooks_Instance.node_with_hooks(node_name="summarize_recent_chapters")
async def summarize_recent_chapters(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "summarize_recent_chapters"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
    _model_name = runtime.context.model
    _user_guidance = state.user_guidance
    _config = runtime.context.config

    prompt_dir = _config.get("prompt_dir")
    result_dir = _config.get("result_dir")

    if result_dir:
        _work_dir = result_dir
    else:
        _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 获得当前章节id
    _current_chapter_id = _user_guidance.get("current_chapter_id")
    if not _current_chapter_id:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "current_chapter_id not found"
        )
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }

    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    # 获得章节蓝图
    if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
        _novel_chapter_blueprint = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_chapter_blueprint not found"
        )
        return {
            "code": 1,
            "err_message": _err_message,
            "messages": Messages(type="end"),
        }

    # 提示词
    def _assemble_prompt():
        # 获取章节概要信息
        _chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id
        )
        # 获取下一章节概要信息
        _next_chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id + 1
        )
        # 获取前文内容
        _recent_texts = get_last_n_chapters_text(_work_dir, _current_chapter_id, n=3)
        _combined_text = "\n\n".join(_recent_texts).strip()
        max_combined_length = 4000
        if len(_combined_text) > max_combined_length:
            _combined_text = _combined_text[-max_combined_length:]

        tmp = {
            "combined_text": _combined_text,
            "novel_number": _current_chapter_id,
            "chapter_title": _chapter_info.get("chapter_title", "未命名"),
            "chapter_role": _chapter_info.get("chapter_role", "常规章节"),
            "chapter_purpose": _chapter_info.get("chapter_purpose", "内容推进"),
            "suspense_level": _chapter_info.get("suspense_level", "中等"),
            "foreshadowing": _chapter_info.get("foreshadowing", "无"),
            "plot_twist_level": _chapter_info.get("plot_twist_level", "★☆☆☆☆"),
            "chapter_summary": _chapter_info.get("chapter_summary", ""),
            "next_chapter_number": _current_chapter_id + 1,
            "next_chapter_title": _next_chapter_info.get("chapter_title", "（未命名）"),
            "next_chapter_role": _next_chapter_info.get("chapter_role", "过渡章节"),
            "next_chapter_purpose": _next_chapter_info.get(
                "chapter_purpose", "承上启下"
            ),
            "next_chapter_summary": _next_chapter_info.get(
                "chapter_summary", "衔接过渡内容"
            ),
            "next_chapter_suspense_level": _next_chapter_info.get(
                "suspense_level", "中等"
            ),
            "next_chapter_foreshadowing": _next_chapter_info.get(
                "foreshadowing", "无特殊伏笔"
            ),
            "next_chapter_plot_twist_level": _next_chapter_info.get(
                "plot_twist_level", "★☆☆☆☆"
            ),
        }
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "ainovel", _NODE_NAME, prompt_dir
        )
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
        _assemble_prompt(),
        _model_name,
    )
    _result = {_NODE_NAME: response.content}
    await write_file_tool.arun(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/{_NODE_NAME}.md",
            "text": json.dumps(_result, ensure_ascii=False),
        }
    )

    return {"code": 0, "err_message": "ok", "data": _result}


# 首章节内容
@Agent_Hooks_Instance.node_with_hooks(node_name="first_chapter_draft")
async def first_chapter_draft(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "first_chapter_draft"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
    _model_name = runtime.context.model
    _user_guidance = state.user_guidance
    _config = runtime.context.config

    prompt_dir = _config.get("prompt_dir")
    result_dir = _config.get("result_dir")

    if result_dir:
        _work_dir = result_dir
    else:
        _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 获得当前章节id
    _current_chapter_id = 1
    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    # 获得小说设定
    if os.path.exists(f"{_work_dir}/novel_extract_setting.md"):
        _novel_setting = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_extract_setting.md"}
        )
        _novel_setting = json.loads(_novel_setting)
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_extract_setting not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得小说架构
    if os.path.exists(f"{_work_dir}/novel_architecture.md"):
        _novel_architecture = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_architecture.md"}
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_architecture not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得章节蓝图
    if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
        _novel_chapter_blueprint = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_chapter_blueprint not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得角色状态
    if os.path.exists(
        f"{_work_dir}/chapter/chapter_{_current_chapter_id}/character_state.md"
    ):
        _character_state = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/character_state.md"
            }
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "character_state not found"
        )
        return {"code": 1, "err_message": _err_message}

    _word_number = _novel_setting["word_number"]
    _chapter_info = get_chapter_info_from_blueprint(
        _novel_chapter_blueprint, _current_chapter_id
    )

    # 提示词
    def _assemble_prompt():
        _characters_involved = ""  # 核心人物
        _key_items = ""  # 关键道具
        _scene_location = ""  # 空间坐标
        _time_constraint = ""  # 时间压力
        tmp = {
            "novel_number": _current_chapter_id,
            "chapter_title": _chapter_info["chapter_title"],
            "chapter_role": _chapter_info["chapter_role"],
            "chapter_purpose": _chapter_info["chapter_purpose"],
            "suspense_level": _chapter_info["suspense_level"],
            "foreshadowing": _chapter_info["foreshadowing"],
            "plot_twist_level": _chapter_info["plot_twist_level"],
            "chapter_summary": _chapter_info["chapter_summary"],
            "word_number": _word_number,
            "novel_architecture": _novel_architecture,
            "character_state": _character_state,
            "characters_involved": _characters_involved,
            "key_items": _key_items,
            "scene_location": _scene_location,
            "time_constraint": _time_constraint,
            "user_guidance": _user_guidance.get("human_in_loop_value", ""),
        }
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "ainovel", _NODE_NAME, prompt_dir
        )
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
        _assemble_prompt(),
        _model_name,
    )

    log_info_set_color(_thread_id, _NODE_NAME, response)
    _result = {"chapter_draft": response.content}
    await write_file_tool.arun(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/chapter_draft.md",
            "text": f"## 第{_current_chapter_id}章 {_chapter_info['chapter_title']}\n\n{response.content}",
        }
    )
    return {"code": 0, "err_message": "ok", "data": _result}


# 下一章节内容
@Agent_Hooks_Instance.node_with_hooks(node_name="next_chapter_draft")
async def next_chapter_draft(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "next_chapter_draft"

    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
    _model_name = runtime.context.model
    _user_guidance = state.user_guidance
    _config = runtime.context.config

    prompt_dir = _config.get("prompt_dir")
    result_dir = _config.get("result_dir")

    if result_dir:
        _work_dir = result_dir
    else:
        _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 获得当前章节id
    _current_chapter_id = _user_guidance.get("current_chapter_id")
    if not _current_chapter_id:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "current_chapter_id not found"
        )
        return {"code": 1, "err_message": _err_message}
    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    # 获得小说设定
    if os.path.exists(f"{_work_dir}/novel_extract_setting.md"):
        _novel_setting = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_extract_setting.md"}
        )
        _novel_setting = json.loads(_novel_setting)
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_extract_setting not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得小说架构
    if os.path.exists(f"{_work_dir}/novel_architecture.md"):
        _novel_architecture = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_architecture.md"}
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_architecture not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得章节蓝图
    if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
        _novel_chapter_blueprint = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "novel_chapter_blueprint not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得角色状态
    if os.path.exists(
        f"{_work_dir}/chapter/chapter_{_current_chapter_id}/character_state.md"
    ):
        _character_state = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/character_state.md"
            }
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "character_state not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获得全局摘要
    if os.path.exists(
        f"{_work_dir}/chapter/chapter_{_current_chapter_id}/global_summary.md"
    ):
        _global_summary = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/global_summary.md"
            }
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "global_summary not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 当前章节摘要
    if os.path.exists(
        f"{_work_dir}/chapter/chapter_{_current_chapter_id}/summarize_recent_chapters.md"
    ):
        _short_summary = await read_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/summarize_recent_chapters.md"
            }
        )
    else:
        _err_message = log_error_set_color(
            _thread_id, _NODE_NAME, "summarize_recent_chapters not found"
        )
        return {"code": 1, "err_message": _err_message}

    # 获取章节概要信息
    _chapter_info = get_chapter_info_from_blueprint(
        _novel_chapter_blueprint, _current_chapter_id
    )

    _word_number = _novel_setting["word_number"]

    # 提示词
    def _assemble_prompt():
        # 获取下一章节概要信息
        _next_chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id + 1
        )
        # 获取前一章的结尾片段
        _recent_texts = get_last_n_chapters_text(_work_dir, _current_chapter_id, n=3)
        _previous_chapter_excerpt = "\n".join(_recent_texts).strip()
        max_combined_length = 500
        if len(_previous_chapter_excerpt) > max_combined_length:
            _previous_chapter_excerpt = _previous_chapter_excerpt[-max_combined_length:]

        _characters_involved = ""  # 核心人物
        _key_items = ""  # 关键道具
        _scene_location = ""  # 空间坐标
        _time_constraint = ""  # 时间压力

        # (TODO：未来加入知识库，对章节进行筛选)
        filtered_context = ""

        tmp = {
            "novel_number": _current_chapter_id,
            "chapter_title": _chapter_info["chapter_title"],
            "chapter_role": _chapter_info["chapter_role"],
            "chapter_purpose": _chapter_info["chapter_purpose"],
            "suspense_level": _chapter_info["suspense_level"],
            "foreshadowing": _chapter_info["foreshadowing"],
            "plot_twist_level": _chapter_info["plot_twist_level"],
            "chapter_summary": _chapter_info["chapter_summary"],
            "next_chapter_number": _current_chapter_id + 1,
            "next_chapter_title": _next_chapter_info.get("chapter_title", "（未命名）"),
            "next_chapter_role": _next_chapter_info.get("chapter_role", "过渡章节"),
            "next_chapter_purpose": _next_chapter_info.get(
                "chapter_purpose", "承上启下"
            ),
            "next_chapter_suspense_level": _next_chapter_info.get(
                "suspense_level", "中等"
            ),
            "next_chapter_foreshadowing": _next_chapter_info.get(
                "foreshadowing", "无特殊伏笔"
            ),
            "next_chapter_plot_twist_level": _next_chapter_info.get(
                "plot_twist_level", "★☆☆☆☆"
            ),
            "next_chapter_summary": _next_chapter_info.get(
                "chapter_summary", "衔接过渡内容"
            ),
            "novel_architecture": _novel_architecture,
            "global_summary": _global_summary,
            "previous_chapter_excerpt": _previous_chapter_excerpt,
            "character_state": _character_state,
            "short_summary": _short_summary,
            "filtered_context": filtered_context,
            "word_number": _word_number,
            "characters_involved": _characters_involved,
            "key_items": _key_items,
            "scene_location": _scene_location,
            "time_constraint": _time_constraint,
            "user_guidance": _user_guidance.get("human_in_loop_value", ""),
        }
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "ainovel", _NODE_NAME, prompt_dir
        )
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
        _assemble_prompt(),
        _model_name,
    )

    _result = {"chapter_draft": response.content}
    await write_file_tool.arun(
        {
            "file_path": f"{_work_dir}/chapter/chapter_{_current_chapter_id}/chapter_draft.md",
            "text": f"## 第{_current_chapter_id}章 {_chapter_info['chapter_title']}\n\n{response.content}",
        }
    )
    return {"code": 0, "err_message": "ok", "data": _result}


# 人工指导
@Agent_Hooks_Instance.node_with_hooks(node_name="human_in_loop_guidance")
async def human_in_loop_guidance(
    state: State, runtime: Runtime[Context]
) -> Command[
    Literal[
        "first_chapter_draft_agent",
        "next_chapter_draft_agent",
    ]
]:
    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir

    _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    # 确定当前属于第几章
    dir_path = Path(f"{_work_dir}")
    file_count = sum(
        1
        for item in dir_path.iterdir()
        if item.is_dir() and item.name.startswith("chapter")
    )
    _current_chapter_id = file_count + 1

    guidance_tip = f"准备开始`第{_current_chapter_id}章节撰写`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`"

    value = interrupt({"message_id": _thread_id, "content": guidance_tip})

    # # 确定当前属于第几章
    # dir_path = Path(f"{_work_dir}")
    # file_count = sum(
    #     1
    #     for item in dir_path.iterdir()
    #     if item.is_dir() and item.name.startswith("chapter")
    # )
    # _current_chapter_id = file_count + 1
    os.makedirs(f"{_work_dir}/chapter/chapter_{_current_chapter_id}", exist_ok=True)

    _new_v = []
    for v in state.messages.value:
        if isinstance(v, BaseMessage):
            v = convert_base_message(v)
        _new_v.append(v)

    if _current_chapter_id == 1:
        return Command(
            goto="first_chapter_draft_agent",  # type: ignore
            update={
                "user_guidance": {
                    "human_in_loop_value": value["human_in_loop"],
                    "current_chapter_id": _current_chapter_id,
                },
                "human_in_loop_node": "first_chapter_draft_agent",
                "messages": Messages(type="override", value=_new_v),
            },
        )
    else:
        return Command(
            goto="next_chapter_draft_agent",  # type: ignore
            update={
                "user_guidance": {
                    "human_in_loop_value": value["human_in_loop"],
                    "current_chapter_id": _current_chapter_id,
                },
                "human_in_loop_node": "next_chapter_draft_agent",
                "messages": Messages(type="override", value=_new_v),
            },
        )


# 人工确认
async def human_in_loop_agree(
    state: State, runtime: Runtime[Context]
) -> Command[
    Literal[
        "first_chapter_draft_agent",
        "next_chapter_draft_agent",
        "human_in_loop_guidance",
        "__end__",
    ]
]:
    # 变量
    _thread_id = runtime.context.thread_id
    _task_dir = runtime.context.task_dir
    _code = state.code
    _human_in_loop_node = state.human_in_loop_node

    _work_dir = os.path.join(_task_dir, _thread_id)
    os.makedirs(_work_dir, exist_ok=True)

    if _code != 0:
        return Command(goto="__end__")

    guidance_tip = "对于上述`章节内容`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`"
    value = interrupt({"message_id": _thread_id, "content": guidance_tip})
    _current_node = _human_in_loop_node

    _new_v = []
    for v in state.messages.value:
        if isinstance(v, BaseMessage):
            v = convert_base_message(v)
        _new_v.append(v)

    if value["human_in_loop"] == "满意":
        # 获得小说设定

        _novel_setting = await read_file_tool.arun(
            {"file_path": f"{_work_dir}/novel_extract_setting.md"}
        )
        _number_of_chapters = json.loads(_novel_setting)["number_of_chapters"]
        _current_chapter_id = state.user_guidance.get(
            "current_chapter_id", float("inf")
        )
        if _current_chapter_id >= _number_of_chapters:
            return Command(
                goto="__end__",
                update={
                    "code": 1,
                    "err_message": "current_chapter_id >= number_of_chapters",
                    "messages": Messages(type="end"),
                },
            )

        return Command(
            goto="human_in_loop_guidance",
            update={
                "messages": Messages(type="override", value=_new_v),
            },
        )
    else:
        tmp = f"<用户修改建议>\n\n{value['human_in_loop']}\n\n</用户修改建议>"
        return Command(
            goto=_current_node,  # type: ignore
            update={
                "user_guidance": {"human_in_loop_value": tmp},
                "messages": Messages(type="override", value=_new_v),
            },
        )


checkpointer = InMemorySaver()
# first chapter draft subgraph
_first_chapter_draft = StateGraph(State, context_schema=Context)
_first_chapter_draft.add_node("create_character_state", create_character_state)
_first_chapter_draft.add_node("first_chapter_draft", first_chapter_draft)
_first_chapter_draft.add_edge(START, "create_character_state")
_first_chapter_draft.add_edge("create_character_state", "first_chapter_draft")
_first_chapter_draft.add_edge("first_chapter_draft", END)
_first_chapter_draft_agent = _first_chapter_draft.compile(checkpointer=checkpointer)

# next chapter draft subgraph
_next_chapter_draft = StateGraph(State, context_schema=Context)
_next_chapter_draft.add_node("global_summary", global_summary)
_next_chapter_draft.add_node("update_character_state", update_character_state)
_next_chapter_draft.add_node("summarize_recent_chapters", summarize_recent_chapters)
_next_chapter_draft.add_node("next_chapter_draft", next_chapter_draft)
_next_chapter_draft.add_edge(START, "global_summary")
_next_chapter_draft.add_edge("global_summary", "update_character_state")
_next_chapter_draft.add_edge("update_character_state", "summarize_recent_chapters")
_next_chapter_draft.add_edge("summarize_recent_chapters", "next_chapter_draft")
_next_chapter_draft.add_edge("next_chapter_draft", END)
_next_chapter_draft_agent = _next_chapter_draft.compile(checkpointer=checkpointer)

# chapter graph
ainovel_chapter_agent = StateGraph(State, context_schema=Context)
ainovel_chapter_agent.add_node("first_chapter_draft_agent", _first_chapter_draft_agent)
ainovel_chapter_agent.add_node("next_chapter_draft_agent", _next_chapter_draft_agent)
ainovel_chapter_agent.add_node("human_in_loop_guidance", human_in_loop_guidance)
ainovel_chapter_agent.add_node("human_in_loop_agree", human_in_loop_agree)
ainovel_chapter_agent.add_edge(START, "human_in_loop_guidance")
ainovel_chapter_agent.add_edge("first_chapter_draft_agent", "human_in_loop_agree")
ainovel_chapter_agent.add_edge("next_chapter_draft_agent", "human_in_loop_agree")
ainovel_chapter_agent = ainovel_chapter_agent.compile(checkpointer=checkpointer)


# png_bytes = ainovel_chapter_agent.get_graph(xray=True).draw_mermaid()
# logger.info(f"ainovel_chapter_agent: \n\n{png_bytes}")
