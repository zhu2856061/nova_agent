# -*- coding: utf-8 -*-
# @Time   : 2025/08/20
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import AsyncGenerator, Dict, Optional

import aiohttp
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nova.core.task.deepresearcher import deepresearcher
from nova.core.utils import handle_event

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


@task_router.post("/deepresearcher", response_model=TaskResponse)
async def deep_researcher_service(request: TaskRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {**request.context, "trace_id": request.trace_id}

        result = await deepresearcher.ainvoke(state, context=context)  # type: ignore
        content = result.get("messages")[-1].content  # type: ignore
        return TaskResponse(
            code=0,
            messages={"role": "assistant", "content": content},  # type: ignore
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@task_router.post("/stream_deepresearcher", response_model=TaskResponse)
async def stream_deep_researcher_service(request: TaskRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {**request.context, "trace_id": request.trace_id}

        async def async_service(trace_id, inputs, context) -> AsyncGenerator:
            session = None
            try:
                session = aiohttp.ClientSession()  # 创建会话
                async for event in deepresearcher.astream_events(
                    inputs, context=context, version="v2"
                ):
                    data = handle_event(trace_id, event)
                    if data:
                        if data["event"] == "error":
                            _response = TaskResponse(code=1, messages=data)
                        else:
                            _response = TaskResponse(code=0, messages=data)

                        yield _response.model_dump_json() + "\n"

                    else:
                        continue

            except Exception as e:
                logger.error(f"Error during streaming: {e}")
                raise
            finally:
                if session is not None:
                    await session.close()  # 确保会话关闭

        return StreamingResponse(
            async_service(request.trace_id, state, context),
            media_type="application/json",  # 流式数据的 MIME 类型
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
