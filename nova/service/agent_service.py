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

from nova import CONF
from nova.agent.ainovel_architect import ainovel_architecture_agent
from nova.agent.ainovel_chapter import ainovel_chapter_agent
from nova.agent.ainovel_interact import core_seed_agent, extract_setting_agent
from nova.agent.memorizer import memorizer_agent
from nova.agent.researcher import researcher_agent
from nova.agent.wechat_researcher import wechat_researcher_agent
from nova.utils import handle_event

logger = logging.getLogger(__name__)


# Define the router
agent_router = APIRouter(
    prefix="/agent",
    tags=["AGENT SERVER"],
    responses={404: {"description": "Not found"}},
)


class AgentRequest(BaseModel):
    trace_id: Optional[str] = Field(None, description="trace_id for logging")
    state: Optional[Dict] = Field(None, description="the input messages of the task")
    context: Dict = Field(..., description="the context runtime dict")
    user_guidance: Optional[Dict] = Field(None, description="the user guidance")
    stream: bool = Field(True, description="whether to stream the response")


class AgentResponse(BaseModel):
    code: int = Field(..., description="code ID")
    messages: Dict = Field(..., description=" response message")


async def service(Task, request: AgentRequest):
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {
            **request.context,
            "trace_id": request.trace_id,
            "task_dir": CONF["SYSTEM"]["task_dir"],
        }
        config = {"configurable": {"thread_id": request.trace_id}}
        stream = request.stream

        if not stream:
            result = await Task.ainvoke(state, context=context, config=config)  # type: ignore
            content = result.get("messages")[-1].content  # type: ignore
            return AgentResponse(
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
                                _response = AgentResponse(code=1, messages=data)
                            else:
                                _response = AgentResponse(code=0, messages=data)

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


@agent_router.post("/researcher", response_model=AgentResponse)
async def researcher_service(request: AgentRequest):
    return await service(researcher_agent, request)


@agent_router.post("/wechat_researcher", response_model=AgentResponse)
async def wechat_researcher_service(request: AgentRequest):
    return await service(wechat_researcher_agent, request)


@agent_router.post("/memorizer")
async def memorizer_service(request: AgentRequest):
    return await service(memorizer_agent, request)


@agent_router.post("/ainovel_architect")
async def ainovel_architect_service(request: AgentRequest):
    return await service(ainovel_architecture_agent, request)


@agent_router.post("/ainovel_chapter")
async def ainovel_chapter_service(request: AgentRequest):
    return await service(ainovel_chapter_agent, request)


@agent_router.post("/ainovel_extract_setting")
async def ainovel_extract_setting_service(request: AgentRequest):
    return await service(extract_setting_agent, request)


@agent_router.post("/ainovel_core_seed")
async def ainovel_core_seed_service(request: AgentRequest):
    return await service(core_seed_agent, request)


@agent_router.post("/human_in_loop")
async def human_in_loop(request: AgentRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        user_guidance = request.user_guidance
        context = {
            **request.context,
            "trace_id": request.trace_id,
            "task_dir": CONF["SYSTEM"]["task_dir"],
        }
        config: RunnableConfig = {"configurable": {"thread_id": request.trace_id}}
        if not user_guidance:
            raise HTTPException(status_code=1, detail="user_guidance is None")

        agent_name = user_guidance.get("agent_name")
        if not agent_name:
            raise HTTPException(status_code=1, detail="agent_name is None")

        if agent_name == "ainovel_architect":
            agent_workflow = ainovel_architecture_agent
        elif agent_name == "ainovel_chapter":
            agent_workflow = ainovel_chapter_agent
        else:
            raise HTTPException(status_code=2, detail="agent_name is not supported")

        async def async_service(trace_id, user_guidance, context) -> AsyncGenerator:
            session = None
            try:
                session = aiohttp.ClientSession()  # 创建会话
                async for event in agent_workflow.astream_events(
                    Command(resume=user_guidance),
                    config=config,
                    context=context,
                    version="v2",
                ):
                    data = handle_event(trace_id, event)
                    if data:
                        if data["event"] == "error":
                            _response = AgentResponse(code=1, messages=data)
                        else:
                            _response = AgentResponse(code=0, messages=data)

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
