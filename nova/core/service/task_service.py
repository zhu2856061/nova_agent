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


def handle_event(trace_id, event):
    try:
        kind = event.get("event")
        data = event.get("data")
        name = event.get("name")
        metadata = event.get("metadata", {})
        parent_ids = event.get("parent_ids", [])

        checkpoint_ns = str(metadata.get("checkpoint_ns", ""))
        langgraph_node = str(metadata.get("langgraph_node", ""))
        langgraph_step = str(metadata.get("langgraph_step", ""))
        run_id = str(event.get("run_id", ""))

        if kind == "on_chain_start":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "RunnableSequence" in _name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chain_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                },
            }

            return ydata

        elif kind == "on_chain_end":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "RunnableSequence" in _name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chain_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                },
            }

        elif kind == "on_chat_model_start":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chat_model_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                },
            }

        elif kind == "on_chat_model_end":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in _name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chat_model_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                    "output": {
                        "content": data["output"].content,
                        "reasoning_content": data["output"].additional_kwargs.get(
                            "reasoning_content", ""
                        ),
                        "tool_calls": data["output"].tool_calls,
                    },
                },
            }

        elif kind == "on_tool_start":
            _name = langgraph_node + "|" + name

            ydata = {
                "event": "on_tool_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                    "input": data.get("input"),
                },
            }

        elif kind == "on_tool_end":
            _name = langgraph_node + "|" + name

            ydata = {
                "event": "on_tool_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                    "output": data["output"] if data.get("output") else "",
                },
            }

        elif kind == "on_chat_model_stream":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in _name and "tool" in _name:
                return None

            content = data["chunk"].content
            if content is None or content == "":
                if not data["chunk"].additional_kwargs.get("reasoning_content"):
                    # Skip empty messages
                    return None
                ydata = {
                    "event": "on_chat_model_stream",
                    "data": {
                        "node_name": _name,
                        "step": langgraph_step,
                        "run_id": run_id,
                        "checkpoint_ns": checkpoint_ns,
                        "parent_ids": parent_ids,
                        "trace_id": trace_id,
                        "output": {
                            "message_id": data["chunk"].id,
                            "reasoning_content": data["chunk"].additional_kwargs[
                                "reasoning_content"
                            ],
                        },
                    },
                }

            else:
                ydata = {
                    "event": "on_chat_model_stream",
                    "data": {
                        "node_name": _name,
                        "step": langgraph_step,
                        "run_id": run_id,
                        "checkpoint_ns": checkpoint_ns,
                        "parent_ids": parent_ids,
                        "trace_id": trace_id,
                        "output": {"message_id": data["chunk"].id, "content": content},
                    },
                }

        else:
            return None

        return ydata

    except Exception as e:
        logger.error(f"Error: {e}")
        ydata = {
            "event": "error",
            "data": {
                "node_name": _name,
                "step": langgraph_step,
                "run_id": run_id,
                "trace_id": trace_id,
                "error": str(e),
            },
        }
        return ydata


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
