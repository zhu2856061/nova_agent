# -*- coding: utf-8 -*-
# @Time   : 2025/08/20
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nova.core.agent.researcher import researcher_agent

logger = logging.getLogger(__name__)


# Define the router
agent_router = APIRouter(
    prefix="/agent",
    tags=["TASK AGENT SERVER"],
    responses={404: {"description": "Not found"}},
)


class AgentRequest(BaseModel):
    trace_id: Optional[str] = Field(None, description="trace_id for logging")
    state: Dict = Field(..., description="the input messages of the task")
    context: Dict = Field(..., description="the context runtime dict")


class AgentResponse(BaseModel):
    code: int = Field(..., description="code ID")
    messages: Dict = Field(..., description=" response message")


def handle_event(trace_id, event):
    try:
        kind = event.get("event")
        data = event.get("data")
        name = event.get("name")
        metadata = event.get("metadata")
        node = (
            ""
            if (metadata.get("checkpoint_ns") is None)  # type: ignore
            else metadata.get("checkpoint_ns").split(":")[0]  # type: ignore
        )
        langgraph_step = (
            ""
            if (metadata.get("langgraph_step") is None)  # type: ignore
            else str(metadata["langgraph_step"])  # type: ignore
        )

        run_id = "" if (event.get("run_id") is None) else str(event["run_id"])

        if kind == "on_chain_start":
            """
            {'event': 'on_chain_start', 'data': {'input': {'researcher_messages': [{'role': 'user', 'content': '请查询网络上的信息，深圳的最近一周内的经济新闻'}]}}, 'name': 'LangGraph', 'tags': [], 'run_id': '98153528-c5cd-4376-a1c6-ce4e27865b55', 'metadata': {}, 'parent_ids': []}
            """
            _name = node or name
            if _name == "RunnableSequence":
                return None

            ydata = {
                "event": "on_chain_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "trace_id": trace_id,
                },
            }

            return ydata

        elif kind == "on_chain_end":
            _name = node or name
            if _name == "RunnableSequence":
                return None

            ydata = {
                "event": "on_chain_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "trace_id": trace_id,
                },
            }

        elif kind == "on_chat_model_start":
            _name = node or name
            if _name == "ChatLiteLLMRouter":
                return None

            ydata = {
                "event": "on_chat_model_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "trace_id": trace_id,
                },
            }

        elif kind == "on_chat_model_end":
            _name = node or name
            if _name == "ChatLiteLLMRouter":  # 去掉非节点中的输出
                return None

            ydata = {
                "event": "on_chat_model_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "trace_id": trace_id,
                    "ouput": {
                        "content": data["output"].content,
                        "reasoning_content": data["output"].additional_kwargs.get(
                            "reasoning_content", ""
                        ),
                        "tool_calls": data["output"].tool_calls,
                    },
                },
            }

        elif kind == "on_tool_start":
            ydata = {
                "event": "on_tool_start",
                "data": {
                    "node_name": name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "trace_id": trace_id,
                    "tool_input": data.get("input"),
                },
            }

        elif kind == "on_tool_end":
            ydata = {
                "event": "on_tool_end",
                "data": {
                    "node_name": name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "trace_id": trace_id,
                    "tool_result": data["output"] if data.get("output") else "",
                },
            }

        # elif kind == "on_chat_model_stream":
        #     content = data["chunk"].content  # type: ignore
        #     if content is None or content == "":
        #         if not data["chunk"].additional_kwargs.get("reasoning_content"):  # type: ignore
        #             # Skip empty messages
        #             return None
        #         ydata = {
        #             "event": "message",
        #             "data": {
        #                 "message_id": data["chunk"].id,  # type: ignore
        #                 "delta": {
        #                     "reasoning_content": (
        #                         data["chunk"].additional_kwargs["reasoning_content"]  # type: ignore
        #                     )
        #                 },
        #             },
        #         }

        #     else:
        #         ydata = {
        #             "event": "message",
        #             "data": {
        #                 "message_id": data["chunk"].id,  # type: ignore
        #                 "delta": {"content": content},
        #             },
        #         }

        else:
            return None
        return ydata

    except Exception as e:
        ydata = {
            "event": "error",
            "data": {
                "id": f"{trace_id}_{node}_{name}_{run_id}",
                "name": name,
                "error": str(e),
            },
        }
        return ydata


@agent_router.post("/researcher", response_model=AgentResponse)
async def researcher_service(request: AgentRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {**request.context, "trace_id": request.trace_id}

        result = await researcher_agent.ainvoke(state, context=context)  # type: ignore
        content = result.get("compressed_research")  # type: ignore
        return AgentResponse(
            code=0,
            messages={"role": "assistant", "content": content},  # type: ignore
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@agent_router.post("/stream_researcher")
async def stream_researcher_service(request: AgentRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        state = request.state
        context = {**request.context, "trace_id": request.trace_id}

        async def async_service(trace_id, inputs, context) -> AsyncGenerator:
            async for event in researcher_agent.astream_events(
                inputs, context=context, version="v2"
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

        return StreamingResponse(
            async_service(request.trace_id, state, context),
            media_type="application/json",  # 流式数据的 MIME 类型
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
