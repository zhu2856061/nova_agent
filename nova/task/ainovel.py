# -*- coding: utf-8 -*-
# @Time   : 2025/10/09 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
from dataclasses import dataclass, field
from typing import Annotated, Literal

from langchain_core.messages import (
    AIMessage,
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
from nova.tools import write_file_tool
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
class AgentState:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    messages: Annotated[list[MessageLikeRepresentation], add_messages]
    architecture_messages: Annotated[list[MessageLikeRepresentation], override_reducer]


@dataclass(kw_only=True)
class ArchitectureState:
    err_message: str = field(
        default="",
        metadata={"description": "The error message to use for the agent."},
    )
    architecture_messages: Annotated[list[MessageLikeRepresentation], add_messages]

    # 0 小说设定
    topic: str = field(
        default="",
        metadata={"description": "The topic of the novel."},
    )
    genre: str = field(
        default="",
        metadata={"description": "The genre of the novel."},
    )
    number_of_chapters: int = field(
        default=0,
        metadata={"description": "The number of chapters in the novel."},
    )
    word_number: int = field(
        default=0,
        metadata={"description": "The word number of each chapter in the novel."},
    )

    # 1 核心种子
    core_seed_result: str = field(
        default="",
        metadata={"description": "The core seed result to use for the agent."},
    )
    # 2 角色动力学
    character_dynamics_result: str = field(
        default="",
        metadata={"description": "The character dynamics result to use for the agent."},
    )
    # 3 世界观
    world_building_result: str = field(
        default="",
        metadata={"description": "The world building result to use for the agent."},
    )
    # 4 三幕式情节架构
    plot_arch_result: str = field(
        default="",
        metadata={"description": "The plot arch result to use for the agent."},
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
    clarify_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )
    architecture_model: str = field(
        default="basic",
        metadata={"description": "The name of llm to use for the agent. "},
    )


# clarify_with_user uses this
class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )


# extract_setting uses this
class ExtractSetting(BaseModel):
    topic: str = Field(
        description="the topic of novel",
    )
    genre: str = Field(
        description="the genre of novel",
    )
    number_of_chapters: str = Field(
        description="the number of chapters in a novel",
    )
    word_number: str = Field(
        description="the word count of each chapter in the novel",
    )


# ######################################################################################
# 函数


# 用户澄清
async def clarify_with_user(
    state: AgentState, runtime: Runtime[Context]
) -> Command[Literal["architecture", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.clarify_model
        _messages = state.messages

        # 提示词
        def _assemble_prompt(messages):
            tmp = {"messages": get_buffer_string(messages)}
            return [
                HumanMessage(
                    content=apply_system_prompt_template("clarify_with_user", tmp)
                )
            ]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ClarifyWithUser)

        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=clarify_with_user | message={response}",
                "pink",
            )
        )
        if response.need_clarification:  # type: ignore
            return Command(
                goto="__end__",
                update={
                    "architecture_messages": [AIMessage(content=response.question)]  # type: ignore
                },
            )
        else:
            return Command(
                goto="architecture",
                update={
                    "architecture_messages": [AIMessage(content=response.verification)]  # type: ignore
                },
            )
    except Exception as e:
        logger.error(
            set_color(
                f"trace_id={_trace_id} | node=clarify_with_user | error={e}", "red"
            )
        )
        return Command(
            goto="__end__",
            update={
                "err_message": f"trace_id={_trace_id} | node=clarify_with_user | error={e}"
            },
        )


# 抽取设定
async def extract_setting(
    state: ArchitectureState, runtime: Runtime[Context]
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

        return Command(
            goto="core_seed",
            update={
                "topic": response.topic,  # type: ignore
                "genre": response.genre,  # type: ignore
                "number_of_chapters": response.number_of_chapters,  # type: ignore
                "word_number": response.word_number,  # type: ignore
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
    state: ArchitectureState, runtime: Runtime[Context]
) -> Command[Literal["character_dynamics", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _topic = state.topic
        _genre = state.genre
        _number_of_chapters = state.number_of_chapters
        _word_number = state.word_number

        # 提示词
        def _assemble_prompt():
            tmp = {
                "topic": _topic,
                "genre": _genre,
                "number_of_chapters": _number_of_chapters,
                "word_number": _word_number,
            }
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

        return Command(
            goto="character_dynamics", update={"core_seed_result": response.content}
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
    state: ArchitectureState, runtime: Runtime[Context]
) -> Command[Literal["world_building", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _core_seed_result = state.core_seed_result

        # 提示词
        def _assemble_prompt():
            tmp = {"core_seed_result": _core_seed_result}
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

        return Command(
            goto="world_building",
            update={"character_dynamics_result": response.content},
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
    state: ArchitectureState, runtime: Runtime[Context]
) -> Command[Literal["plot_arch", "__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _core_seed_result = state.core_seed_result

        # 提示词
        def _assemble_prompt():
            tmp = {"core_seed_result": _core_seed_result}
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

        return Command(
            goto="plot_arch", update={"world_building_result": response.content}
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
    state: ArchitectureState, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    try:
        # 变量
        _trace_id = runtime.context.trace_id
        _model_name = runtime.context.architecture_model
        _task_dir = runtime.context.task_dir
        _topic = state.topic
        _genre = state.genre
        _number_of_chapters = state.number_of_chapters
        _word_number = state.word_number
        _core_seed_result = state.core_seed_result
        _character_dynamics_result = state.character_dynamics_result
        _world_building_result = state.world_building_result

        _work_dir = os.path.join(_task_dir, _trace_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt():
            tmp = {
                "core_seed_result": _core_seed_result,
                "character_dynamics_result": _character_dynamics_result,
                "world_building_result": _world_building_result,
            }
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
            f"主题：{_topic},类型：{_genre},篇幅：约{_number_of_chapters}章（每章{_word_number}字）\n\n"
            "#=== 1) 核心种子 ===\n"
            f"{_core_seed_result}\n\n"
            "#=== 2) 角色动力学 ===\n"
            f"{_character_dynamics_result}\n\n"
            "#=== 3) 世界观 ===\n"
            f"{_world_building_result}\n\n"
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
            update={
                "plot_arch_result": response.content,
                "architecture_messages": final_content,
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


#
# Agent - Workflow

# architecture subgraph
architecture_subgraph_builder = StateGraph(ArchitectureState, context_schema=Context)
architecture_subgraph_builder.add_node("extract_setting", extract_setting)
architecture_subgraph_builder.add_node("core_seed", core_seed)
architecture_subgraph_builder.add_node("character_dynamics", character_dynamics)
architecture_subgraph_builder.add_node("world_building", world_building)
architecture_subgraph_builder.add_node("plot_arch", plot_arch)
architecture_subgraph_builder.add_edge(START, "extract_setting")
architecture_subgraph = architecture_subgraph_builder.compile()


# supervisor researcher graph
graph_builder = StateGraph(AgentState, context_schema=Context)
graph_builder.add_node("clarify_with_user", clarify_with_user)
graph_builder.add_node("architecture", architecture_subgraph)
graph_builder.add_edge(START, "clarify_with_user")
ainovel = graph_builder.compile()
