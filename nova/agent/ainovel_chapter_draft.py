# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Annotated, Dict, Literal

from langchain_core.messages import (
    HumanMessage,
    MessageLikeRepresentation,
)
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova.llms import get_llm_by_type
from nova.prompts.ainovel import apply_system_prompt_template
from nova.tools import read_file_tool, write_file_tool
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
class State:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    chapter_messages: Annotated[list[MessageLikeRepresentation], override_reducer]

    # 用户介入的信息
    user_guidance: str = field(
        default="",
        metadata={"description": "The user guidance to use for the agent."},
    )

    middle_result: Dict = field(
        default_factory=dict,
        metadata={"description": "The middle result to use for the agent."},
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
    chapter_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )


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
        if os.path.exists(f"{work_dir}/chapter/第{c}章.md"):
            chap_text = read_file_tool.run(
                {"file_path": f"{work_dir}/chapter/第{c}章.md"}
            )
            texts.append(chap_text)
        else:
            texts.append("")
    return texts


# 章节内容
async def first_chapter_draft(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.chapter_model
        _middle_result = state.middle_result
        _current_chapter_id = _middle_result.get("current_chapter_id", 1)

        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        os.makedirs(f"{_work_dir}/chapter", exist_ok=True)

        #
        if os.path.exists(f"{_work_dir}/novel_architecture.md"):
            _novel_architecture = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_architecture.md"}
            )
        else:
            _novel_architecture = ""
        if _novel_architecture is None:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=first_chapter_draft | error=novel_architecture is None"
                },
            )

        if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
            _novel_chapter_blueprint = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
            )
        else:
            _novel_chapter_blueprint = ""
        if _novel_chapter_blueprint is None:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=first_chapter_draft | error=novel_chapter_blueprint is None"
                },
            )

        # 提示词
        def _assemble_prompt(
            characters_involved="",
            key_items="",
            scene_location="",
            time_constraint="",
            user_guidance="",
        ):
            # 获取章节信息
            chapter_info = get_chapter_info_from_blueprint(
                _novel_chapter_blueprint, _current_chapter_id
            )
            chapter_title = chapter_info["chapter_title"]
            chapter_role = chapter_info["chapter_role"]
            chapter_purpose = chapter_info["chapter_purpose"]
            suspense_level = chapter_info["suspense_level"]
            foreshadowing = chapter_info["foreshadowing"]
            plot_twist_level = chapter_info["plot_twist_level"]
            chapter_summary = chapter_info["chapter_summary"]
            _word_number = _middle_result.get("word_number", 1000)

            tmp = {
                "novel_number": _current_chapter_id,
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
                "user_guidance": user_guidance,
                "novel_setting": _novel_architecture,
            }

            return [
                HumanMessage(
                    content=apply_system_prompt_template("first_chapter_draft", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        # 第一章特殊处理
        response = await _get_llm().ainvoke(_assemble_prompt())

        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=first_chapter_draft | message={response}",
                "pink",
            )
        )

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/第{_current_chapter_id}章.md",
                "text": response.content,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=first_chapter_draft | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=first_chapter_draft | error={e}"
            },
        )


# 下一章节内容
async def next_chapter_draft(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.chapter_model
        _middle_result = state.middle_result
        _current_chapter_id = _middle_result.get("current_chapter_id", 2)

        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        os.makedirs(f"{_work_dir}/chapter", exist_ok=True)

        #
        if os.path.exists(f"{_work_dir}/novel_architecture.md"):
            _novel_architecture = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_architecture.md"}
            )
        else:
            _novel_architecture = ""
        if not _novel_architecture:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=next_chapter_draft | error=novel_architecture is None"
                },
            )

        if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
            _novel_chapter_blueprint = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
            )
        else:
            _novel_chapter_blueprint = ""
        if not _novel_chapter_blueprint:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=next_chapter_draft | error=novel_chapter_blueprint is None"
                },
            )

        # 全局摘要
        if os.path.exists(f"{_work_dir}/global_summary.md"):
            _global_summary = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/global_summary.md"}
            )
        else:
            _global_summary = ""
        if not _global_summary:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=next_chapter_draft | error=global_summary is None"
                },
            )

        # 角色变化
        if os.path.exists(f"{_work_dir}/character_state.md"):
            _character_state = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/character_state.md"}
            )
        else:
            _character_state = ""
        if not _character_state:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=next_chapter_draft | error=character_state is None"
                },
            )

        # 最近三章的摘要
        if os.path.exists(f"{_work_dir}/summarize_recent_chapters.md"):
            _summarize_recent_chapters = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/summarize_recent_chapters.md"}
            )
        else:
            _summarize_recent_chapters = ""
        if not _summarize_recent_chapters:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=next_chapter_draft | error=summarize_recent_chapters is None"
                },
            )

        # 提示词
        def _assemble_prompt(
            filtered_context="",
            characters_involved="",
            key_items="",
            scene_location="",
            time_constraint="",
            user_guidance="",
        ):
            # 获取章节信息
            chapter_info = get_chapter_info_from_blueprint(
                _novel_chapter_blueprint, _current_chapter_id
            )

            # 获取下一章节信息
            next_chapter_info = get_chapter_info_from_blueprint(
                _novel_chapter_blueprint, _current_chapter_id + 1
            )

            chapter_title = chapter_info["chapter_title"]
            chapter_role = chapter_info["chapter_role"]
            chapter_purpose = chapter_info["chapter_purpose"]
            suspense_level = chapter_info["suspense_level"]
            foreshadowing = chapter_info["foreshadowing"]
            plot_twist_level = chapter_info["plot_twist_level"]
            chapter_summary = chapter_info["chapter_summary"]

            next_chapter_title = next_chapter_info.get("chapter_title", "（未命名）")
            next_chapter_role = next_chapter_info.get("chapter_role", "过渡章节")
            next_chapter_purpose = next_chapter_info.get("chapter_purpose", "承上启下")
            next_suspense_level = next_chapter_info.get("suspense_level", "中等")
            next_foreshadowing = next_chapter_info.get("foreshadowing", "无特殊伏笔")
            next_plot_twist_level = next_chapter_info.get("plot_twist_level", "★☆☆☆☆")
            next_chapter_summary = next_chapter_info.get(
                "chapter_summary", "衔接过渡内容"
            )

            # 获取前文内容和摘要
            recent_texts = get_last_n_chapters_text(_work_dir, _current_chapter_id, n=3)
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=next_chapter_draft | message=前文内容长度：{len(recent_texts)}",
                    "pink",
                )
            )

            # 获取前一章结尾
            previous_chapter_excerpt = ""
            for text in reversed(recent_texts):
                if text.strip():
                    previous_chapter_excerpt = text[-800:] if len(text) > 800 else text
                    break

            _word_number = _middle_result.get("word_number", 1000)

            # (TODO：未来加入知识库，对章节进行筛选)
            filtered_context = ""

            tmp = {
                "global_summary": _global_summary,
                "previous_chapter_excerpt": previous_chapter_excerpt,
                "character_state": _character_state,
                "short_summary": _summarize_recent_chapters,
                "novel_number": _current_chapter_id,
                "chapter_title": chapter_title,
                "chapter_role": chapter_role,
                "chapter_purpose": chapter_purpose,
                "suspense_level": suspense_level,
                "foreshadowing": foreshadowing,
                "plot_twist_level": plot_twist_level,
                "chapter_summary": chapter_summary,
                "next_chapter_number": _current_chapter_id + 1,
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
                "user_guidance": user_guidance,
            }

            return [
                HumanMessage(
                    content=apply_system_prompt_template("next_chapter_draft", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        # 章节生成
        response = await _get_llm().ainvoke(_assemble_prompt())

        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=next_chapter_draft | message={response}",
                "pink",
            )
        )

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/第{_current_chapter_id}章.md",
                "text": response.content,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=next_chapter_draft | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=next_chapter_draft | error={e}"
            },
        )


# 章节内容扩写
async def enrich_chapter(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.chapter_model
        _middle_result = state.middle_result
        _current_chapter_id = _middle_result.get("current_chapter_id", 1)
        _word_number = _middle_result.get("word_number", 1000)

        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        os.makedirs(f"{_work_dir}/chapter", exist_ok=True)

        if os.path.exists(f"{_work_dir}/chapter/第{_current_chapter_id}章.md"):
            _chapter_text = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/chapter/第{_current_chapter_id}章.md"}
            )
        else:
            _chapter_text = ""

        if not _chapter_text:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=enrich_chapter | error=chapter_text is None"
                },
            )

        # 提示词
        def _assemble_prompt():
            tmp = {
                "word_number": _word_number,
                "chapter_text": _chapter_text,
            }
            return [
                HumanMessage(
                    content=apply_system_prompt_template("enrich_chapter", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        while len(_chapter_text) < 0.8 * _word_number:
            response = await _get_llm().ainvoke(_assemble_prompt())
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=enrich_chapter | message={response}",
                    "pink",
                )
            )
            _chapter_text = response.content

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/chapter/第{_current_chapter_id}章.md",
                "text": _chapter_text,
            }
        )

        return Command(goto="__end__")

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=enrich_chapter | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=enrich_chapter | error={e}"
            },
        )


# 为生成下一章节，准备信息【全局摘要，历史前3章节摘要，用户状态变化】
async def chapter_abstract(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.chapter_model

        _middle_result = state.middle_result
        _current_chapter_id = _middle_result.get("current_chapter_id", 1) + 1

        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        os.makedirs(f"{_work_dir}/chapter", exist_ok=True)

        if os.path.exists(f"{_work_dir}/novel_architecture.md"):
            _novel_architecture = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_architecture.md"}
            )
        else:
            _novel_architecture = ""
        if not _novel_architecture:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=chapter_abstract | error=novel_architecture is None"
                },
            )

        if os.path.exists(f"{_work_dir}/novel_chapter_blueprint.md"):
            _novel_chapter_blueprint = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/novel_chapter_blueprint.md"}
            )
        else:
            _novel_chapter_blueprint = ""
        if not _novel_chapter_blueprint:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=chapter_abstract | error=novel_chapter_blueprint is None"
                },
            )

        if os.path.exists(f"{_work_dir}/chapter/第{_current_chapter_id - 1}章.md"):
            _chapter_text = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/chapter/第{_current_chapter_id}章.md"}
            )
        else:
            _chapter_text = ""
        if not _chapter_text:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=chapter_abstract | error=chapter_text is None"
                },
            )

        if os.path.exists(f"{_work_dir}/global_summary.md"):
            _old_global_summary = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/global_summary.md"}
            )
        else:
            _old_global_summary = ""

        if os.path.exists(f"{_work_dir}/character_state.md"):
            _old_character_state = await read_file_tool.arun(
                {"file_path": f"{_work_dir}/character_state.md"}
            )
        else:
            _old_character_state = ""

        # 获取章节信息
        _chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id
        )
        # 获取下一章节信息
        _next_chapter_info = get_chapter_info_from_blueprint(
            _novel_chapter_blueprint, _current_chapter_id + 1
        )
        # 获取前文内容和摘要
        _recent_texts = get_last_n_chapters_text(_work_dir, _current_chapter_id, n=3)
        _combined_text = "\n".join(_recent_texts).strip()
        if not _combined_text:
            return Command(
                goto="__end__",
                update={
                    "err_message": f"trace_id={_trace_id} | node=chapter_abstract | error=recent_texts is None"
                },
            )

        # 限制组合文本长度
        max_combined_length = 4000
        if len(_combined_text) > max_combined_length:
            _combined_text = _combined_text[-max_combined_length:]

        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=chapter_abstract | message=前文内容长度：{len(_combined_text)}",
                "pink",
            )
        )

        # 提示词
        def _assemble_prompt(target):
            if target == "global_summary":
                tmp = {
                    "chapter_text": _chapter_text,
                    "global_summary": _old_global_summary,
                }
                return [
                    HumanMessage(
                        content=apply_system_prompt_template("global_summary", tmp)
                    )
                ]
            elif target == "character_state":
                tmp = {
                    "chapter_text": _chapter_text,
                    "character_state": _old_character_state,
                }
                return [
                    HumanMessage(
                        content=apply_system_prompt_template(
                            "update_character_state", tmp
                        )
                    )
                ]
            else:
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
                    "next_chapter_title": _next_chapter_info.get(
                        "chapter_title", "（未命名）"
                    ),
                    "next_chapter_role": _next_chapter_info.get(
                        "chapter_role", "过渡章节"
                    ),
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

            return [
                HumanMessage(
                    content=apply_system_prompt_template(
                        "summarize_recent_chapters", tmp
                    )
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        new_global_summary = await _get_llm().ainvoke(
            _assemble_prompt("global_summary")
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=chapter_abstract | message={new_global_summary}",
                "pink",
            )
        )
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/global_summary.md",
                "text": new_global_summary.content,
            }
        )

        new_character_state = await _get_llm().ainvoke(
            _assemble_prompt("character_state")
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=chapter_abstract | message={new_character_state}",
                "pink",
            )
        )
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/character_state.md",
                "text": new_character_state.content,
            }
        )

        summarize_recent_chapters = await _get_llm().ainvoke(
            _assemble_prompt("summarize_recent_chapters")
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=chapter_abstract | message={summarize_recent_chapters}",
                "pink",
            )
        )
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/summarize_recent_chapters.md",
                "text": summarize_recent_chapters.content,
            }
        )
        _middle_result = {**_middle_result, "current_chapter_id": _current_chapter_id}

        return Command(goto="__end__", update={"middle_result": _middle_result})

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=chapter_abstract | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=chapter_abstract | error={e}"
            },
        )


# 判断是否结束
async def check_final(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["next_chapter_draft", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _middle_result = state.middle_result
        _current_chapter_id = _middle_result.get("current_chapter_id", 1)
        _number_of_chapters = _middle_result.get("number_of_chapters")

        if _current_chapter_id > _number_of_chapters:
            return Command(goto="__end__")
        else:
            return Command(goto="next_chapter_draft")

    except Exception as e:
        logger.error(
            set_color(f"trace_id={_trace_id} | node=check_final | error={e}", "red")
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=check_final | error={e}"
            },
        )


# chapter next subgraph
_next_chapter_agent = StateGraph(State, context_schema=Context)
_next_chapter_agent.add_node("chapter_abstract", chapter_abstract)
_next_chapter_agent.add_node("next_chapter_draft", next_chapter_draft)
_next_chapter_agent.add_node("enrich_chapter", enrich_chapter)
_next_chapter_agent.add_edge(START, "chapter_abstract")
_next_chapter_agent.add_edge("chapter_abstract", "next_chapter_draft")
_next_chapter_agent.add_edge("next_chapter_draft", "enrich_chapter")
ainovel_next_chapter_agent = _next_chapter_agent.compile()


# chapter subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("first_chapter_draft", first_chapter_draft)
_agent.add_node("enrich_chapter", enrich_chapter)
_agent.add_node("check_final", check_final)
_agent.add_node("next_chapter_draft", ainovel_next_chapter_agent)
_agent.add_edge(START, "first_chapter_draft")
_agent.add_edge("first_chapter_draft", "enrich_chapter")
_agent.add_edge("enrich_chapter", "check_final")
_agent.add_edge("next_chapter_draft", "check_final")

ainovel_chapter_draft_agent = _agent.compile()
