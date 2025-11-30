# -*- coding: utf-8 -*-
# @Time   : 2025/11/30 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field

from nova.agent.ainovel_architect import ainovel_architecture_agent
from nova.agent.ainovel_chapter import ainovel_chapter_agent
from nova.llms import get_llm_by_type
from nova.prompts.template import apply_prompt_template, get_prompt
from nova.utils import (
    set_color,
)

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
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


# ######################################################################################
# 函数


# 用户澄清
async def clarify_with_user(
    state: State, runtime: Runtime[Context]
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

        # 执行
        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        logger.info(
            set_color(
                f"trace_id={_trace_id} | node=clarify_with_user | message={response}",
                "pink",
            )
        )

        # 路由
        if response.need_clarification:  # type: ignore
            return Command(
                goto="__end__",
                update={
                    "messages": [AIMessage(content=response.question)]  # type: ignore
                },
            )
        else:
            return Command(
                goto="architecture",
                update={
                    "architecture_messages": [
                        HumanMessage(content=response.verification)  # type: ignore
                    ]
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


# supervisor researcher graph
graph_builder = StateGraph(State, context_schema=Context)
graph_builder.add_node("clarify_with_user", clarify_with_user)
graph_builder.add_node("architecture", ainovel_architecture_agent)
graph_builder.add_node("chapter", ainovel_chapter_agent)
graph_builder.add_edge(START, "clarify_with_user")
graph_builder.add_edge("architecture", "chapter")

checkpointer = InMemorySaver()
ainovel = graph_builder.compile(checkpointer=checkpointer)
# ainovel = graph_builder.compile()

# png_bytes = ainovel.get_graph(xray=True).draw_mermaid()
# logger.info(png_bytes)
# 将二进制数据写入文件（指定保存路径和文件名）
# with open("./logs/ainovel_graph.png", "wb") as f:
#     f.write(png_bytes)
