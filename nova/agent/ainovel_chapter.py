# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Literal

from langchain_core.messages import (
    HumanMessage,
)
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

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
    # chapter_messages: Annotated[list[MessageLikeRepresentation], override_reducer]

    # 用户介入的信息
    user_guidance: str = field(
        default="",
        metadata={"description": "The user guidance to use for the agent."},
    )

    middle_result: Dict = field(
        default_factory=dict,
        metadata={"description": "The middle result to use for the agent."},
    )
    human_in_loop_node: str = field(
        default="",
        metadata={"description": "The next node to use for the agent."},
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
    chunk_size: int = field(
        default=2,
        metadata={"description": "The chunk size to use for the agent."},
    )
    max_chapter_length: int = field(
        default=5,
        metadata={"description": "The max chapter length to use for the agent."},
    )


# ######################################################################################
# 函数


# 章节处理路由选择
async def route_chapter_blueprint(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["chapter_blueprint", "chunk_chapter_blueprint"]]:
    # 变量
    _trace_id = runtime.context.trace_id
    _max_chapter_length = runtime.context.max_chapter_length
    _middle_result = state.middle_result
    _number_of_chapters: int = _middle_result.get("number_of_chapters", 2)

    if _number_of_chapters <= _max_chapter_length:
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=route_chapter_blueprint | goto=chapter_blueprint",
                "pink",
            )
        )
        return Command(goto="chapter_blueprint")
    else:
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=route_chapter_blueprint | goto=chunk_chapter_blueprint",
                "pink",
            )
        )
        return Command(goto="chunk_chapter_blueprint")


# 章节目录
async def chapter_blueprint(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["save_chapter_blueprint", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.chapter_model
        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        _user_guidance = state.user_guidance
        _middle_result = state.middle_result
        _number_of_chapters: int = _middle_result.get("number_of_chapters", 3)

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
                    "err_message": f"trace_id={_trace_id} | node=chapter_blueprint | error=novel_architecture is None"
                },
            )

        # 提示词
        def _assemble_prompt():
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

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(_assemble_prompt())
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=chapter_blueprint | message={response}",
                "pink",
            )
        )

        _middle_result = {**_middle_result, "chapter_blueprint": response.content}

        return Command(
            goto="save_chapter_blueprint",
            update={"middle_result": _middle_result},
        )

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


# 递归单章节目录
async def chunk_chapter_blueprint(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["save_chapter_blueprint", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.chapter_model
        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        _user_guidance = state.user_guidance
        _middle_result = state.middle_result
        _number_of_chapters: int = _middle_result.get("number_of_chapters", 3)
        _chunk_size = runtime.context.chunk_size

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
                    "err_message": f"trace_id={_trace_id} | node=chapter_blueprint | error=novel_architecture is None"
                },
            )

        # 提示词
        def _assemble_prompt(chapter_list, start, end):
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

        current_start = 1
        final_chapter_blueprint = []

        while current_start <= _number_of_chapters:
            current_end = min(current_start + _chunk_size, _number_of_chapters)
            chapter_list = "\n\n".join(final_chapter_blueprint[-200:])

            response = await _get_llm().ainvoke(
                _assemble_prompt(chapter_list, current_start, current_end)
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
            **_middle_result,
            "chapter_blueprint": "\n\n".join(final_chapter_blueprint),
        }

        return Command(
            goto="save_chapter_blueprint",
            update={"middle_result": _middle_result},
        )

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


# 保存目录数据
async def save_chapter_blueprint(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)
        _middle_result = state.middle_result

        #
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
                f"trace_id={_trace_id} | node=save_chapter_blueprint | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=save_chapter_blueprint | error={e}"
            },
        )


# chapter subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("route_chapter_blueprint", route_chapter_blueprint)
_agent.add_node("chapter_blueprint", chapter_blueprint)
_agent.add_node("chunk_chapter_blueprint", chunk_chapter_blueprint)
_agent.add_node("save_chapter_blueprint", save_chapter_blueprint)
_agent.add_edge(START, "route_chapter_blueprint")
ainovel_chapter_agent = _agent.compile()
