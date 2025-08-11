# -*- coding: utf-8 -*-
# @Time   : 2025/05/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.llm_router import llm_router

logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
# Define constants for better readability and easier modification


@asynccontextmanager
async def lifespan(app: FastAPI):
    """定义 FastAPI 生命周期事件"""
    # 启动时加载分词器和模型
    logger.info("init eveything")
    yield
    # 关闭时清理资源
    logger.info("clear everything")


app = FastAPI(
    title="Eva Service",
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

# init
# Include the LLM router
app.include_router(llm_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# if __name__ == "__main__":
#     import uvicorn
#     logger.info("Starting Nova Agent API Server")
#     uvicorn.run(
#         "app:app",
#         host="0.0.0.0",
#         port=2021,
#         reload=False,
#         log_level="info",
#     )
