# -*- coding: utf-8 -*-
# @Time   : 2025/05/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nova.service.agent_service import agent_router
from nova.service.chat_service import chat_router
from nova.service.task_service import task_router

logger = logging.getLogger(__name__)


# --- FastAPI App Initialization ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """定义 FastAPI 生命周期事件"""
    # 启动时加载分词器和模型
    logger.info("init eveything")
    yield
    # 关闭时清理资源
    logger.info("clear everything")


app = FastAPI(
    title="Nova Service",
    description="一个通用的Agent服务",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# init
# Include the LLM router
app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(task_router)


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀Starting Nova Agent API Server🚀")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=2021,
        reload=False,
        log_level="info",
    )
