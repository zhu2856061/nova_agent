# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nova.core.llms import get_llm_by_type

logger = logging.getLogger(__name__)


# Define the router
chat_router = APIRouter(
    prefix="/chat",
    tags=["LLM SERVER"],
    responses={404: {"description": "Not found"}},
)


class LLMRequest(BaseModel):
    trace_id: Optional[str] = Field(None, description="trace_id for logging")
    llm_dtype: str = Field(..., description="llm_dtype")
    messages: List[Dict] = Field(..., description="messages dict")
    config: Optional[Dict] = Field(None, description="config dict")


class LLMResponse(BaseModel):
    code: int = Field(..., description="code ID")
    messages: Dict = Field(..., description=" response message")


@chat_router.post("/llm", response_model=LLMResponse)
async def llm_server(request: LLMRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        model = get_llm_by_type(request.llm_dtype)
        if request.config:
            result = await model.ainvoke(request.messages, **request.config)
        else:
            result = await model.ainvoke(request.messages)

        return LLMResponse(
            code=0, messages={"role": "assistant", "content": result.content}
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.post("/stream_llm")
async def stream_llm_server(request: LLMRequest):
    """LLM Server"""
    if not request:
        raise HTTPException(status_code=400, detail="Input instances cannot be empty")

    try:
        model = get_llm_by_type(request.llm_dtype)

        # 定义一个生成器函数来逐步生成响应
        async def async_generate_response() -> AsyncGenerator:
            # 假设模型提供了异步生成器接口
            if request.config:
                async for response in model.astream(request.messages, **request.config):
                    if response.content:
                        llm_response = LLMResponse(
                            code=0, messages={"content": response.content}
                        )
                        yield llm_response.model_dump_json() + "\n"
            else:
                async for response in model.astream(request.messages):
                    if response.content:
                        llm_response = LLMResponse(
                            code=0, messages={"content": response.content}
                        )
                        yield llm_response.model_dump_json() + "\n"

        return StreamingResponse(
            async_generate_response(),
            media_type="application/json",  # 流式数据的 MIME 类型
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
