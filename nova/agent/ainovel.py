# -*- coding: utf-8 -*-
# @Time   : 2025/11/30 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging

from langchain_core.messages import (
    HumanMessage,
    get_buffer_string,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field

from nova.agent.ainovel_architect import ainovel_architecture_agent
from nova.agent.ainovel_chapter import ainovel_chapter_agent
from nova.llms import get_llm_by_type
from nova.model.agent import Context, Messages, State
from nova.prompts.template import apply_prompt_template, get_prompt
from nova.utils.log_utils import (
    log_error_set_color,
    log_info_set_color,
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
async def clarify_with_user(state: State, runtime: Runtime[Context]):
    _NODE_NAME = "clarify_with_user"
    try:
        # 变量
        _thread_id = runtime.context.thread_id
        _model_name = runtime.context.model
        _messages = state.messages.value

        # 提示词
        def _assemble_prompt(messages):
            tmp = {"messages": get_buffer_string(messages)}
            _prompt_tamplate = get_prompt("ainovel", "clarify_with_user")
            return [HumanMessage(content=apply_prompt_template(_prompt_tamplate, tmp))]

        # LLM
        def _get_llm():
            return get_llm_by_type(_model_name).with_structured_output(ClarifyWithUser)

        # 执行
        response = await _get_llm().ainvoke(_assemble_prompt(_messages))
        log_info_set_color(_thread_id, _NODE_NAME, response)

        if not isinstance(response, ClarifyWithUser):
            return Command(
                goto="__end__",
                update={
                    "code": 1,
                    "err_message": "ClarifyWithUser is not a valid response",
                    "messages": Messages(type="end"),
                },
            )

        # 路由
        if response.need_clarification:
            return {
                "code": 0,
                "err_message": "ok",
                "messages": Messages(type="end"),
                "data": {_NODE_NAME: response.model_dump()},
            }
        else:
            return {"messages": [HumanMessage(content=response.verification)]}

    except Exception as e:
        _err_message = log_error_set_color(_thread_id, _NODE_NAME, e)
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "messages": Messages(type="end"),
                "err_message": _err_message,
            },
        )


# 全流程写小说 graph
graph_builder = StateGraph(State, context_schema=Context)
graph_builder.add_node("clarify_with_user", clarify_with_user)
graph_builder.add_node("architecture", ainovel_architecture_agent)
graph_builder.add_node("chapter", ainovel_chapter_agent)
graph_builder.add_edge(START, "clarify_with_user")
graph_builder.add_edge("architecture", "chapter")
graph_builder.add_edge("chapter", END)
checkpointer = InMemorySaver()
ainovel = graph_builder.compile(checkpointer=checkpointer)

# png_bytes = ainovel.get_graph(xray=True).draw_mermaid()
# logger.info(png_bytes)
# 将二进制数据写入文件（指定保存路径和文件名）
# with open("./logs/ainovel_graph.png", "wb") as f:
#     f.write(png_bytes)
