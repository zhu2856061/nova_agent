# -*- coding: utf-8 -*-
# @Time   : 2025/11/20
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

import aiohttp
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from langchain_core.runnables.config import RunnableConfig
from langgraph.types import Command

from nova.agent import (
    chat_agent,
    memorizer_agent,
    researcher_agent,
    super_nova_agent,
    theme_slicer_agent,
)
from nova.model.service import SuperAgentRequest, SuperAgentResponse
from nova.service.handle_event import handle_event

logger = logging.getLogger(__name__)


# Define the router
agent_router = APIRouter(
    prefix="/agent",
    tags=["AGENT SERVER"],
    responses={404: {"description": "Not found"}},
)


# Central agent registry - maintains all agent mappings
AGENT_REGISTRY = {
    "super_nova": super_nova_agent,
    "themeslicer": theme_slicer_agent,
    "memorizer": memorizer_agent,
    "chat": chat_agent,
    "researcher": researcher_agent,
}


VALID_TOKENS = ["1234"]


def add_register_agent_endpoints(name, agent_instance):
    AGENT_REGISTRY[name] = agent_instance


# Dependency for getting agent by name
def get_agent(agent_name: str):
    agent = AGENT_REGISTRY.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return agent


# Shared streaming handler
async def stream_agent_events(
    instance, trace_id, state, context, config: dict
) -> AsyncGenerator[str]:
    """Generic streaming handler for all agents"""
    state["code"] = 0
    try:
        async with aiohttp.ClientSession() as session:  # Auto-closing context manager
            if context.get("is_human_in_loop"):
                req = Command(resume=state.get("user_guidance"))
            else:
                req = state
            async for event in instance.astream_events(
                req, config=config, context=context, version="v2"
            ):
                response = handle_event(trace_id, event)  # type: ignore
                if response:
                    if response.get("event_name") == "error":
                        res = SuperAgentResponse(
                            code=1,
                            data=response.get("event_info", {}),
                        ).model_dump_json()

                        yield res
                        return

                    try:
                        res = SuperAgentResponse(
                            code=0, err_message="ok", data=response
                        ).model_dump_json()
                    except Exception:
                        res = SuperAgentResponse(
                            code=1, err_message="data is not json serializable"
                        ).model_dump_json()

                    yield res

    except Exception as e:
        logger.error(f"Streaming error (trace_id={trace_id}): {str(e)}", exc_info=True)
        error_response = SuperAgentResponse(
            code=500, err_message=f"Streaming failed: {str(e)}"
        )
        yield error_response.model_dump_json()
    finally:
        if session is not None:
            await session.close()  # 确保会话关闭


@agent_router.post("/service")
async def agent_service(request: SuperAgentRequest):
    if not request:
        logger.error("error: Input instances cannot be empty", exc_info=True)
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        trace_id = request.trace_id
        context = request.context
        state = request.state
        stream = request.stream

        # 获取 thread_id
        thread_id = context.get("thread_id")
        if not thread_id:
            logger.error("herror: thread_id is required", exc_info=True)
            return SuperAgentResponse(
                code=1, data={"err_message": "thread_id is required"}
            )

        # 获取 agent
        agent = get_agent(context.get("agent", ""))
        if agent is None:
            logger.error(
                f"error: agent {context.get('agent')} not found", exc_info=True
            )
            return SuperAgentResponse(
                code=1, data={"err_message": f"agent {context.get('agent')} not found"}
            )

        # 创建 config
        config = context.get("config", {"recursion_limit": 100})
        assert isinstance(config, dict)
        config.update({"configurable": {"thread_id": thread_id}})

        # 若是 is_human_in_loop 则需要判断 state.user_guidance 字段存在
        user_guidance = request.state.get("user_guidance")
        is_human_in_loop = context.get("is_human_in_loop", False)
        if is_human_in_loop and not user_guidance:
            logger.error(
                "error: is_human_in_loop is True, user_guidance is required",
                exc_info=True,
            )
            return SuperAgentResponse(
                code=1,
                data={
                    "err_message": "is_human_in_loop is True, user_guidance is required"
                },
            )

        if not stream:
            if is_human_in_loop:
                response = await agent.ainvoke(
                    Command(resume=user_guidance),
                    context=context,
                    config=RunnableConfig(**config),
                )
            else:
                response = await agent.ainvoke(
                    state, context=context, config=RunnableConfig(**config)
                )
            return SuperAgentResponse(code=0, data=response)

        else:
            return StreamingResponse(
                stream_agent_events(agent, trace_id, state, context, config),
                media_type="application/json",  # 流式数据的 MIME 类型
            )

    except Exception as e:
        logger.error(
            f"service error (trace_id={request.trace_id}): {str(e)}",
            exc_info=True,
        )
        return SuperAgentResponse(
            code=1,
            data={"err_message": f"Service error: {str(e)}"},
        )


# 存储活跃的 WebSocket 连接（可选，用于广播等场景）
active_connections: list[WebSocket] = []


async def agent_ws_message(request: SuperAgentRequest, websocket: WebSocket):
    if not request:
        logger.error("error: Input instances cannot be empty", exc_info=True)
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")
    try:
        trace_id = request.trace_id
        context = request.context
        state = request.state
        stream = request.stream

        # 获取 thread_id
        thread_id = context.get("thread_id")
        if not thread_id:
            logger.error("herror: thread_id is required", exc_info=True)

            await websocket.send_text(
                SuperAgentResponse(
                    code=0, data={"err_message": "thread_id is required"}
                ).model_dump_json()
            )
            return

        # 获取 agent
        agent = get_agent(context.get("agent", ""))
        if agent is None:
            logger.error(
                f"error: agent {context.get('agent')} not found", exc_info=True
            )
            await websocket.send_text(
                SuperAgentResponse(
                    code=0,
                    data={"err_message": f"agent {context.get('agent')} not found"},
                ).model_dump_json()
            )
            return

        # 创建 config
        config = context.get("config", {"recursion_limit": 100})
        assert isinstance(config, dict)
        config.update({"configurable": {"thread_id": thread_id}})

        # 若是 human_in_loop 则需要判断 state.user_guidance 字段存在
        user_guidance = request.state.get("user_guidance")
        is_human_in_loop = context.get("human_in_loop", False)
        if is_human_in_loop and not user_guidance:
            logger.error(
                "error: human_in_loop is True, user_guidance is required", exc_info=True
            )
            await websocket.send_text(
                SuperAgentResponse(
                    code=0,
                    data={
                        "err_message": "human_in_loop is True, user_guidance is required"
                    },
                ).model_dump_json()
            )
            return

        if not stream:
            if is_human_in_loop:
                response = await agent.ainvoke(
                    Command(resume=user_guidance),
                    context=context,
                    config=RunnableConfig(**config),
                )
            else:
                response = await agent.ainvoke(
                    state, context=context, config=RunnableConfig(**config)
                )

            await websocket.send_text(
                SuperAgentResponse(code=0, data=response).model_dump_json()
            )

        else:
            async for chunk in stream_agent_events(
                agent, trace_id, state, context, config
            ):
                await websocket.send_text(chunk)

    except Exception as e:
        logger.error(
            f"service error (trace_id={request.trace_id}): {str(e)}",
            exc_info=True,
        )
        await websocket.send_text(
            SuperAgentResponse(
                code=0,
                data={"err_message": f"Service error: {str(e)}"},
            ).model_dump_json()
        )
        return


@agent_router.websocket("/ws")
async def agent_websocket_stream(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token or token not in VALID_TOKENS:
        await websocket.close(code=1008)
        raise WebSocketDisconnect(code=1008)

    # 1. 接受客户端连接
    await websocket.accept()
    # 将连接加入活跃列表（可选）
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            agent_request = SuperAgentRequest.model_validate_json(data)
            logger.info(
                f"收到请求 - trace_id: {agent_request.trace_id}, data: {agent_request}"
            )
            # 异步处理，不阻塞接收下一条消息
            asyncio.create_task(agent_ws_message(agent_request, websocket))

    # 捕获客户端断开连接的异常
    except WebSocketDisconnect:
        # 从活跃列表移除断开的连接
        active_connections.remove(websocket)
        logger.info("客户端断开连接")
    # finally:
    #     # 确保连接关闭（可选，FastAPI 会自动处理，但显式关闭更健壮）
    #     await websocket.close()
