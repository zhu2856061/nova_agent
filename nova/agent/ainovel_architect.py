# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Annotated, Dict, Literal

from langchain_core.messages import (
    HumanMessage,
    MessageLikeRepresentation,
    get_buffer_string,
)
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
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
    architecture_messages: Annotated[list[MessageLikeRepresentation], add_messages]

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
) -> Command[Literal["human_in_loop_agree", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _messages = state.architecture_messages
        _user_guidance = state.user_guidance

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

        return Command(
            goto="human_in_loop_agree",
            update={
                "middle_result": _middle_result,
                "human_in_loop_node": "extract_setting",
            },
        )

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
) -> Command[Literal["human_in_loop_agree", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _middle_result = state.middle_result
        _user_guidance = state.user_guidance

        # 提示词
        def _assemble_prompt():
            tmp = {**_middle_result, "user_guidance": _user_guidance}
            print("===>", tmp)
            return [
                HumanMessage(content=apply_system_prompt_template("core_seed", tmp))
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(_assemble_prompt())
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=core_seed | message={response}",
                "pink",
            )
        )

        _middle_result = {**_middle_result, "core_seed": response.content}

        return Command(
            goto=["human_in_loop_agree"],
            update={
                "middle_result": _middle_result,
                "human_in_loop_node": "core_seed",
            },
        )

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
) -> Command[Literal["human_in_loop_agree", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _middle_result = state.middle_result
        _user_guidance = state.user_guidance
        _task_dir = runtime.context.task_dir

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt():
            tmp = {**_middle_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("character_dynamics", tmp)
                )
            ]

        def _assemble_character_state_prompt(tmp):
            return [
                HumanMessage(
                    content=apply_system_prompt_template("create_character_state", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(_assemble_prompt())
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=character_dynamics | message={response}",
                "pink",
            )
        )

        _middle_result = {**_middle_result, "character_dynamics": response.content}

        response = await _get_llm().ainvoke(
            _assemble_character_state_prompt(_middle_result)
        )
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=character_dynamics | message={response}",
                "pink",
            )
        )

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/character_state.md",
                "text": response.content,
            }
        )

        return Command(
            goto=["human_in_loop_agree"],
            update={
                "middle_result": _middle_result,
                "human_in_loop_node": "character_dynamics",
            },
        )

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
) -> Command[Literal["human_in_loop_agree", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _middle_result = state.middle_result
        _user_guidance = state.user_guidance

        # 提示词
        def _assemble_prompt():
            tmp = {**_middle_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("world_building", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(_assemble_prompt())
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=world_building | message={response}",
                "pink",
            )
        )

        _middle_result = {**_middle_result, "world_building": response.content}

        return Command(
            goto=["human_in_loop_agree"],
            update={
                "middle_result": _middle_result,
                "human_in_loop_node": "world_building",
            },
        )

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
) -> Command[Literal["human_in_loop_agree", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _middle_result = state.middle_result
        _user_guidance = state.user_guidance

        # 提示词
        def _assemble_prompt():
            tmp = {**_middle_result, "user_guidance": _user_guidance}
            return [
                HumanMessage(content=apply_system_prompt_template("plot_arch", tmp))
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name)

        response = await _get_llm().ainvoke(_assemble_prompt())
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=plot_arch | message={response}",
                "pink",
            )
        )

        _middle_result = {**_middle_result, "plot_arch": response.content}

        return Command(
            goto=["human_in_loop_agree"],
            update={
                "middle_result": _middle_result,
                "human_in_loop_node": "plot_arch",
            },
        )

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
) -> Command[Literal["human_in_loop_agree", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _user_guidance = state.user_guidance
        _middle_result = state.middle_result
        _number_of_chapters: int = _middle_result["number_of_chapters"]

        _work_dir = os.path.join(runtime.context.task_dir, _trace_id)

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
        def _assemble_overall_prompt():
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

        def _assemble_chunk_prompt(chapter_list, start, end):
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

        if _number_of_chapters <= 10:  # 小于10章的一次性产出
            response = await _get_llm().ainvoke(_assemble_overall_prompt())
            logger.info(
                set_color(
                    f"trace_id={_trace_id} | node=chapter_blueprint | message={response}",
                    "pink",
                )
            )

            _middle_result = {**_middle_result, "chapter_blueprint": response.content}
        else:
            current_start = 1
            final_chapter_blueprint = []
            while current_start <= _number_of_chapters:
                current_end = min(current_start + 10, _number_of_chapters)
                chapter_list = "\n\n".join(final_chapter_blueprint[-200:])

                response = await _get_llm().ainvoke(
                    _assemble_chunk_prompt(chapter_list, current_start, current_end)
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
            goto=["human_in_loop_agree"],
            update={
                "middle_result": _middle_result,
                "human_in_loop_node": "chapter_blueprint",
            },
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


async def summarize_architecture(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _task_dir = runtime.context.task_dir
        _middle_result = state.middle_result

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

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

        return Command(
            goto=["__end__"],
            update={
                "architecture_messages": final_content,
            },
        )

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
        "__end__",
    ]
]:
    _trace_id = runtime.context.trace_id
    _human_in_loop_node = state.human_in_loop_node
    if _human_in_loop_node == "core_seed":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "基于上述生成信息准备开始`构建核心种子`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`",
            }
        )
        _result = user_guidance["result"]
        return Command(goto="core_seed", update={"user_guidance": _result})

    elif _human_in_loop_node == "character_dynamics":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "基于上述生成信息准备开始`构建角色`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`",
            }
        )
        _result = user_guidance["result"]
        return Command(goto="character_dynamics", update={"user_guidance": _result})

    elif _human_in_loop_node == "world_building":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "基于上述生成信息准备开始`构建世界观`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`",
            }
        )
        _result = user_guidance["result"]
        return Command(goto="world_building", update={"user_guidance": _result})

    elif _human_in_loop_node == "plot_arch":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "基于上述生成信息准备开始`构建三幕式情节`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`",
            }
        )
        _result = user_guidance["result"]
        return Command(goto="plot_arch", update={"user_guidance": _result})

    elif _human_in_loop_node == "chapter_blueprint":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "基于上述生成信息准备开始`构建章节蓝图`，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`",
            }
        )
        _result = user_guidance["result"]
        return Command(goto="chapter_blueprint", update={"user_guidance": _result})

    else:
        return Command(goto="__end__")


# 人工指导
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
        "summarize_architecture",
        "__end__",
    ]
]:
    _trace_id = runtime.context.trace_id
    _human_in_loop_node = state.human_in_loop_node
    _middle_result = state.middle_result

    if _human_in_loop_node == "extract_setting":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "对于上述`抽取的信息`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`",
            }
        )
        _result = user_guidance["result"]
        if _result == "满意":
            return Command(
                goto="human_in_loop_guidance",
                update={
                    "user_guidance": _result,
                    "human_in_loop_node": "core_seed",
                },
            )
        else:
            tmp = json.dumps(_middle_result, ensure_ascii=False)
            _result = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{_result}\n\n</用户修改建议>"

            return Command(
                goto="extract_setting",
                update={
                    "user_guidance": _result,
                },
            )

    elif _human_in_loop_node == "core_seed":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "对于上述`核心种子`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`",
            }
        )
        _result = user_guidance["result"]
        if _result == "满意":
            return Command(
                goto="human_in_loop_guidance",
                update={
                    "user_guidance": _result,
                    "human_in_loop_node": "character_dynamics",
                },
            )
        else:
            tmp = _middle_result["core_seed"]
            _result = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{_result}\n\n</用户修改建议>"

            return Command(
                goto="core_seed",
                update={
                    "user_guidance": _result,
                },
            )

    elif _human_in_loop_node == "character_dynamics":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "对于上述`角色信息`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`",
            }
        )
        _result = user_guidance["result"]
        if _result == "满意":
            return Command(
                goto="human_in_loop_guidance",
                update={
                    "user_guidance": _result,
                    "human_in_loop_node": "world_building",
                },
            )
        else:
            tmp = _middle_result["character_dynamics"]
            _result = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{_result}\n\n</用户修改建议>"

            return Command(
                goto="character_dynamics",
                update={
                    "user_guidance": _result,
                },
            )

    elif _human_in_loop_node == "world_building":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "对于上述`世界观`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`",
            }
        )
        _result = user_guidance["result"]
        if _result == "满意":
            return Command(
                goto="human_in_loop_guidance",
                update={
                    "user_guidance": _result,
                    "human_in_loop_node": "plot_arch",
                },
            )
        else:
            tmp = _middle_result["world_building"]
            _result = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{_result}\n\n</用户修改建议>"

            return Command(
                goto="world_building",
                update={
                    "user_guidance": _result,
                },
            )

    elif _human_in_loop_node == "plot_arch":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "对于上述`三幕式情节架构`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`",
            }
        )
        _result = user_guidance["result"]
        if _result == "满意":
            return Command(
                goto="chapter_blueprint",
                update={
                    "user_guidance": _result,
                    "human_in_loop_node": "plot_arch",
                },
            )
        else:
            tmp = _middle_result["plot_arch"]
            _result = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{_result}\n\n</用户修改建议>"

            return Command(
                goto="plot_arch",
                update={
                    "user_guidance": _result,
                },
            )

    elif _human_in_loop_node == "chapter_blueprint":
        user_guidance = interrupt(
            {
                "message_id": _trace_id,
                "content": "对于上述`构建章节蓝图`是否满意，不满意的话，可以输入修改建议，若是满意的话，可以输入`满意`",
            }
        )
        _result = user_guidance["result"]
        if _result == "满意":
            return Command(
                goto="summarize_architecture",
                update={
                    "user_guidance": _result,
                    "human_in_loop_node": "chapter_blueprint",
                },
            )
        else:
            tmp = _middle_result["chapter_blueprint"]
            _result = f"<上一次生成的结果>\n\n{tmp}\n\n</上一次生成的结果>\n\n<用户修改建议>\n\n{_result}\n\n</用户修改建议>"

            return Command(
                goto="chapter_blueprint",
                update={
                    "user_guidance": _result,
                },
            )

    else:
        return Command(goto="__end__")


# architecture subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("extract_setting", extract_setting)
_agent.add_node("core_seed", core_seed)
_agent.add_node("character_dynamics", character_dynamics)
_agent.add_node("world_building", world_building)
_agent.add_node("plot_arch", plot_arch)
_agent.add_node("chapter_blueprint", chapter_blueprint)
_agent.add_node("summarize_architecture", summarize_architecture)

_agent.add_node("human_in_loop_guidance", human_in_loop_guidance)
_agent.add_node("human_in_loop_agree", human_in_loop_agree)

_agent.add_edge(START, "extract_setting")


ainovel_architecture_agent = _agent.compile()

png_bytes = ainovel_architecture_agent.get_graph(xray=True).draw_mermaid()
logger.info(png_bytes)
