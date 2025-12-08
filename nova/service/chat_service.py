# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import AsyncGenerator, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from nova.llms import get_llm_by_type
from nova.model.agent import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)


# Define the router
chat_router = APIRouter(
    prefix="/chat",
    tags=["CHAT SERVER"],
    responses={404: {"description": "Not found"}},
)


async def _stream_responses(
    model, messages: List, config: Dict, model_kwargs: Dict
) -> AsyncGenerator[str, None]:
    """抽取流式响应处理逻辑，消除代码冗余"""
    try:
        async for response in model.astream(messages, config=config, **model_kwargs):
            if response.content:
                yield (
                    AgentResponse(
                        code=0,
                        data={
                            "event": "llm_stream",
                            "data": {"content": response.content},
                        },
                    ).model_dump_json()
                    + "\n"
                )
            if response.additional_kwargs:
                yield (
                    AgentResponse(
                        code=0,
                        data={
                            "event": "llm_stream",
                            "data": response.additional_kwargs,
                        },
                    ).model_dump_json()
                    + "\n"
                )
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        # 生成错误响应供客户端捕获
        yield (
            AgentResponse(
                code=1, data={"error": f"Streaming failed: {str(e)}"}
            ).model_dump_json()
            + "\n"
        )
        raise  # 重新抛出以便外层捕获日志


@chat_router.post("/llm")
async def llm_server(request: AgentRequest):
    """LLM 服务接口，支持流式和非流式响应"""
    if not request:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    try:
        # 提取请求参数并统一处理
        trace_id = request.trace_id
        context = request.context
        state = request.state
        stream = request.stream
        model_kwargs = context.config or {}  # 统一模型参数格式

        # 构建配置信息
        config = {"configurable": {"thread_id": context.thread_id}}

        # 获取LLM实例
        model = get_llm_by_type(context.model)
        if not model:
            raise HTTPException(
                status_code=400, detail=f"Unsupported model: {context.model}"
            )

        # 非流式处理
        if not stream:
            response = await model.ainvoke(
                state.messages.value,
                config=config,  # type: ignore
                **model_kwargs,
            )
            return AgentResponse(code=0, data={"content": response.content})

        # 流式处理
        return StreamingResponse(
            _stream_responses(model, state.messages.value, config, model_kwargs),
            media_type="application/json",
        )

    except HTTPException:
        # 已定义的HTTP异常直接抛出
        raise
    except Exception as e:
        logger.error(f"LLM service error (trace_id={trace_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")
