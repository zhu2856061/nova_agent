# -*- coding: utf-8 -*-
# @Time   : 2026/02/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field

from .super_agent import SuperContext, SuperState


class SuperAgentRequest(BaseModel):
    trace_id: str = Field("default", description="the trace_id")
    context: SuperContext = Field(..., description="the context runtime dict")
    state: SuperState = Field(..., description="the input messages of the task")
    stream: bool = Field(True, description="whether to stream the response")


class SuperAgentResponse(BaseModel):
    code: int = Field(..., description="code ID")
    err_message: str = Field(default="", description="error message")
    data: Dict = Field(default={}, description="data")
