# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from typing import Annotated, Dict, List

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


class State(BaseModel):
    code: int = Field(default=0, description="The code to use for the agent.")
    err_message: str = Field(default="", description="error message")
    user_guidance: Dict = Field(default={}, description="user guidance")
    # messages: List[Dict] = Field(default=[], description="messages")
    messages: Annotated[List[MessageLikeRepresentation], add_messages] = Field(
        default=[], description="messages"
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
