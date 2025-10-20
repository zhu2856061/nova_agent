# -*- coding: utf-8 -*-
# @Time   : 2025/08/20
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import AsyncGenerator, Dict, Optional

import aiohttp
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from nova.task.ainovel import ainovel
from nova.task.deepresearcher import deepresearcher
from nova.utils import handle_event

logger = logging.getLogger(__name__)


# Define the router
task_router = APIRouter(
    prefix="/task",
    tags=["TASK SERVER"],
    responses={404: {"description": "Not found"}},
)


class TaskRequest(BaseModel):
    trace_id: Optional[str] = Field(None, description="trace_id for logging")
    state: Dict = Field(..., description="the input messages of the task")
    context: Dict = Field(..., description="the context runtime dict")
    user_guidance: Optional[Dict] = Field(None, description="the user guidance")
    stream: bool = Field(True, description="whether to stream the response")


class TaskResponse(BaseModel):
    code: int = Field(..., description="code ID")
    messages: Dict = Field(..., description=" response message")


async def service(Task, request: TaskRequest):
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {**request.context, "trace_id": request.trace_id}
        config = {"configurable": {"thread_id": request.trace_id}}
        stream = request.stream

        if not stream:
            result = await Task.ainvoke(state, context=context, config=config)  # type: ignore
            content = result.get("messages")[-1].content  # type: ignore
            return TaskResponse(
                code=0,
                messages={"role": "assistant", "content": content},  # type: ignore
            )
        else:

            async def async_service(
                trace_id, inputs, context, config
            ) -> AsyncGenerator:
                session = None
                try:
                    session = aiohttp.ClientSession()  # 创建会话
                    async for event in Task.astream_events(
                        inputs, config=config, context=context, version="v2"
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
                async_service(request.trace_id, state, context, config),
                media_type="application/json",  # 流式数据的 MIME 类型
            )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@task_router.post("/deepresearcher", response_model=TaskResponse)
async def deepresearcher_service(request: TaskRequest):
    return await service(deepresearcher, request)


@task_router.post("/ainovel", response_model=TaskResponse)
async def ainovel_service(request: TaskRequest):
    """LLM Server"""
    return await service(ainovel, request)


@task_router.post("/human_in_loop")
async def human_in_loop(request: TaskRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        user_guidance = request.user_guidance
        context = {**request.context, "trace_id": request.trace_id}
        config: RunnableConfig = {"configurable": {"thread_id": request.trace_id}}
        if not user_guidance:
            raise HTTPException(status_code=1, detail="user_guidance is None")

        task_name = user_guidance.get("task_name")
        if not task_name:
            raise HTTPException(status_code=1, detail="task_name is None")

        if task_name == "ai_novel":
            task_workflow = ainovel
        elif task_name == "deep_researcher":
            task_workflow = deepresearcher
        else:
            raise HTTPException(status_code=2, detail="task_name is not supported")

        async def async_service(trace_id, user_guidance, context) -> AsyncGenerator:
            session = None
            try:
                session = aiohttp.ClientSession()  # 创建会话
                async for event in task_workflow.astream_events(
                    Command(resume=user_guidance),
                    config=config,
                    context=context,
                    version="v2",
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
            async_service(request.trace_id, user_guidance, context),
            media_type="application/json",  # 流式数据的 MIME 类型
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
