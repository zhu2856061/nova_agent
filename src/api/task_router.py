# -*- coding: utf-8 -*-
# @Time   : 2025/08/20
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.task.deep_researcher import graph

logger = logging.getLogger(__name__)


# Define the router
task_router = APIRouter(
    prefix="/task",
    tags=["TASK AGENT SERVER"],
    responses={404: {"description": "Not found"}},
)


class TaskRequest(BaseModel):
    trace_id: Optional[str] = Field(None, description="trace_id for logging")
    state: Dict = Field(..., description="the input messages of the task")
    context: Dict = Field(..., description="the context runtime dict")


class TaskResponse(BaseModel):
    code: int = Field(..., description="code ID")
    messages: Dict = Field(..., description=" response message")


@task_router.post("/deep_researcher", response_model=TaskResponse)
async def deep_researcher_server(request: TaskRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {**request.context, "trace_id": request.trace_id}

        result = await graph.ainvoke(state, context=context)  # type: ignore
        content = result.get("messages")[-1].content  # type: ignore
        return TaskResponse(
            code=0,
            messages={"role": "assistant", "content": content},  # type: ignore
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
