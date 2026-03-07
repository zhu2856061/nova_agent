# -*- coding: utf-8 -*-
# @Time   : 2025/11/20
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from typing import AsyncGenerator

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.runnables.config import RunnableConfig
from langgraph.types import Command

from nova.agent import super_nova_agent, theme_slicer_agent
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
}


# Dependency for getting agent by name
def get_agent(agent_name: str):
    agent = AGENT_REGISTRY.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return agent


# Shared streaming handler
async def stream_agent_events(
    instance, trace_id, state, context, config: dict
) -> AsyncGenerator:
    """Generic streaming handler for all agents"""
    try:
        async with aiohttp.ClientSession() as session:  # Auto-closing context manager
            async for event in instance.astream_events(
                state, config=config, context=context, version="v2"
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


@agent_router.post("/human_in_loop")
async def human_in_loop(request: SuperAgentRequest):
    if not request:
        logger.error(
            "human_in_loop error: Input instances cannot be empty", exc_info=True
        )
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        trace_id = request.trace_id
        context = request.context
        stream = request.stream

        thread_id = context.get("thread_id")
        if not thread_id:
            logger.error("human_in_loop error: thread_id is required", exc_info=True)
            return SuperAgentResponse(
                code=1, data={"err_message": "thread_id is required"}
            )
        config = RunnableConfig(configurable={"thread_id": thread_id})

        user_guidance = request.state.get("user_guidance")
        if not user_guidance:
            logger.error(
                "human_in_loop error: user_guidance is required", exc_info=True
            )
            raise HTTPException(status_code=400, detail="user_guidance is required")

        agent_name = user_guidance.get("agent_name")
        if not agent_name:
            logger.error("human_in_loop error: agent_name is required", exc_info=True)
            raise HTTPException(status_code=400, detail="agent_name is required")

        agent = get_agent(agent_name)
        if not stream:
            response = await agent.ainvoke(
                Command(resume=user_guidance), context=context, config=config
            )
            return SuperAgentResponse(code=0, data=response)

        # Streaming handler for human-in-loop
        async def stream_human_in_loop() -> AsyncGenerator:
            try:
                async with aiohttp.ClientSession() as session:
                    async for event in agent.astream_events(
                        Command(resume=user_guidance),
                        config=config,
                        context=context,
                        version="v2",
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
                                    code=1,
                                    err_message="data is not json serializable",
                                ).model_dump_json()

                            yield res

            except Exception as e:
                logger.error(
                    f"Human-in-loop error (trace_id={trace_id}): {str(e)}",
                    exc_info=True,
                )
                error_response = SuperAgentResponse(
                    code=500, err_message=f"Interaction failed: {str(e)}"
                )
                yield error_response.model_dump_json() + "\n"
            finally:
                if session is not None:
                    await session.close()  # 确保会话关闭

        return StreamingResponse(
            stream_human_in_loop(),
            media_type="application/json",  # 流式数据的 MIME 类型
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logger.error(f"Unexpected error in human-in-loop: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


async def agent_service(agent, request: SuperAgentRequest):
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        trace_id = request.trace_id
        context = request.context
        state = request.state
        stream = request.stream

        thread_id = context.get("thread_id")
        if not thread_id:
            logger.error("human_in_loop error: thread_id is required", exc_info=True)
            return SuperAgentResponse(
                code=1, data={"err_message": "thread_id is required"}
            )

        config = {"configurable": {"thread_id": thread_id}}

        if not stream:
            response = await agent.ainvoke(state, context=context, config=config)
            return SuperAgentResponse(code=0, data=response)
        else:
            return StreamingResponse(
                stream_agent_events(agent, trace_id, state, context, config),
                media_type="application/json",  # 流式数据的 MIME 类型
            )
    except Exception as e:
        logger.error(
            f"Agent service error (trace_id={request.trace_id}): {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")


# 动态注册函数
def register_agent_endpoints():
    """Dynamically register all agent endpoints from the registry"""
    for agent_name, agent_instance in AGENT_REGISTRY.items():
        # 增加一层闭包，固定当前的 agent_name
        def create_endpoint_factory(current_agent_name):
            async def endpoint(
                request: SuperAgentRequest,
                agent=Depends(
                    lambda: get_agent(current_agent_name)
                ),  # 使用固定的 current_agent_name
            ):
                return await agent_service(agent, request)

            return endpoint

        # 为每个 agent 生成独立的 endpoint
        endpoint = create_endpoint_factory(agent_name)

        # 注册端点
        agent_router.post(f"/{agent_name}", name=f"{agent_name}_service")(endpoint)


# 动态新增函数
def add_register_agent_endpoints(agent_name, agent_instance):
    """Dynamically register all agent endpoints from the registry"""

    # 增加一层闭包，固定当前的 agent_name
    def create_endpoint_factory():
        async def endpoint(
            request: SuperAgentRequest,
            agent=Depends(lambda: agent_instance),  # 使用固定的 current_agent_name
        ):
            return await agent_service(agent, request)

        return endpoint

    # 为每个 agent 生成独立的 endpoint
    endpoint = create_endpoint_factory()

    # 注册端点
    agent_router.post(f"/{agent_name}", name=f"{agent_name}_service")(endpoint)

    AGENT_REGISTRY[agent_name] = agent_instance


# Register all agent endpoints
register_agent_endpoints()
