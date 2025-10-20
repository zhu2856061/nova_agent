# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
from dataclasses import dataclass, field
from typing import Annotated, Dict, Literal

from langchain_core.messages import (
    HumanMessage,
    MessageLikeRepresentation,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph, add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from nova.llms import get_llm_by_type
from nova.prompts.ainovel import apply_system_prompt_template
from nova.tools import write_file_tool
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
) -> Command[Literal["core_seed", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _messages = state.architecture_messages

        # 提示词
        def _assemble_prompt(messages):
            tmp = {"messages": get_buffer_string(messages)}
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

        return Command(goto="core_seed", update={"middle_result": _middle_result})

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
) -> Command[Literal["character_dynamics", "__end__"]]:
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
            goto="character_dynamics", update={"middle_result": _middle_result}
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
) -> Command[Literal["create_character_state", "__end__"]]:
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
                    content=apply_system_prompt_template("character_dynamics", tmp)
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

        return Command(
            goto="create_character_state", update={"middle_result": _middle_result}
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


# 初始化角色状态
async def create_character_state(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["world_building", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _task_dir = runtime.context.task_dir
        _middle_result = state.middle_result

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt():
            tmp = {**_middle_result}
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
                f"trace_id={_trace_id} | node=create_character_state | message={response}",
                "pink",
            )
        )

        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/character_state.md",
                "text": response.content,
            }
        )

        return Command(goto="world_building")

    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=create_character_state | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=create_character_state | error={e}"
            },
        )


# 世界观
async def world_building(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["plot_arch", "__end__"]]:
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

        return Command(goto="plot_arch", update={"middle_result": _middle_result})

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
        _model_name = runtime.context.architecture_model
        _task_dir = runtime.context.task_dir
        _middle_result = state.middle_result
        _user_guidance = state.user_guidance

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

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
            f"{response.content}\n"
        )
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/novel_architecture.md",
                "text": final_content,
            }
        )

        return Command(
            goto="__end__",
            update={"architecture_messages": final_content},
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


# 人工指导
async def human_in_loop(
    state: State, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    _trace_id = runtime.context.trace_id
    user_guidance = interrupt(
        {
            "message_id": _trace_id,
            "content": "基础上述生成信息，是否需要人工指导，需要的话直接输入指导内容，不需要的话直接输入`不需要`",
        }
    )
    _result = user_guidance["result"]

    return Command(goto="__end__", update={"user_guidance": _result})


# architecture subgraph
_agent = StateGraph(State, context_schema=Context)
_agent.add_node("extract_setting", extract_setting)
_agent.add_node("core_seed", core_seed)
_agent.add_node("character_dynamics", character_dynamics)
_agent.add_node("create_character_state", create_character_state)
_agent.add_node("world_building", world_building)
_agent.add_node("plot_arch", plot_arch)
_agent.add_node("human_in_loop", human_in_loop)

_agent.add_edge(START, "extract_setting")
_agent.add_edge("core_seed", "human_in_loop")
_agent.add_edge("character_dynamics", "human_in_loop")
_agent.add_edge("world_building", "human_in_loop")

checkpointer = InMemorySaver()
ainovel_architecture_agent = _agent.compile(checkpointer=checkpointer)
