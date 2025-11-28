# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, cast

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph.message import (
    BaseMessageChunk,
    # add_messages,
    convert_to_messages,
    message_chunk_to_message,
)  # 关键导入！这是 LangGraph 的内置转换器
from pydantic import BaseModel, Field

# from typing_extensions import TypedDict
# from nova.utils.common import override_reducer


class Messages(BaseModel):
    type: str = Field(default="", description="type")
    value: List[MessageLikeRepresentation] = Field(default=[], description="messages")


def override_reducer(current_value: Messages, new_value: Any):
    """
    支持两种写入方式：
    - 普通追加：直接返回 BaseMessage 或 List[BaseMessage]
    - 强制覆盖：返回 {"type": "override", "value": [...]}
    """
    if isinstance(new_value, Messages):
        value = new_value.value
        if not isinstance(value, list):
            value = [value]
        value = [
            message_chunk_to_message(cast(BaseMessageChunk, m))
            for m in convert_to_messages(value)
        ]

        if new_value.type == "override":
            return Messages(type="override", value=value)  # type: ignore
        else:
            value = operator.add(current_value.value, value)
            return Messages(type="override", value=value)  # type: ignore

    else:
        if not isinstance(new_value, list):
            new_value = [new_value]
        new_value = [
            message_chunk_to_message(cast(BaseMessageChunk, m))
            for m in convert_to_messages(new_value)
        ]
        value = operator.add(current_value.value, new_value)
        return Messages(value=value)


class State(BaseModel):
    code: int = Field(default=0, description="The code to use for the agent.")
    err_message: str = Field(default="ok", description="error message")
    user_guidance: Dict = Field(default={}, description="user guidance")
    messages: Annotated[Messages, override_reducer] = Field(
        default=Messages(type="", value=[]), description="user guidance"
    )
    data: Dict = Field(default={}, description="data")
    human_in_loop_node: str = Field(
        default="",
        description="human_in_loop node for the agent.",
    )


class Context(BaseModel):
    thread_id: str = Field("default", description="the thread_id")
    task_dir: str = Field("", description="the task dir")
    model: str = Field("basic", description="the model")
    models: Dict = Field(default={}, description="the model dict")
    config: Dict = Field(default={}, description="the config dict")


class AgentRequest(BaseModel):
    trace_id: str = Field("default", description="the trace_id")
    context: Context = Field(..., description="the context runtime dict")
    state: State = Field(..., description="the input messages of the task")
    stream: bool = Field(True, description="whether to stream the response")


class AgentResponse(BaseModel):
    code: int = Field(..., description="code ID")
    err_message: str = Field(default="", description="error message")
    data: Dict = Field(default={}, description="data")
