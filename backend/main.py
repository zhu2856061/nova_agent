# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nova import CONF
from nova.service.agent_service import agent_router

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
    title=CONF.SYSTEM.NAME,
    description=CONF.SYSTEM.DESC,
    version=CONF.SYSTEM.VERSION,
    lifespan=lifespan,
    debug=CONF.SYSTEM.DEBUG,
)
# 启用压缩，减少传输字节数
# from fastapi.middleware.gzip import GZipMiddleware
# app.add_middleware(GZipMiddleware, minimum_size=1000)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {
        "message": f"{CONF.SYSTEM.NAME} 服务正在运行",
        "version": f"{CONF.SYSTEM.VERSION}",
    }


# Include the LLM router
# app.include_router(chat_router)
app.include_router(agent_router)


# # 添加全局异常处理器
# @app.exception_handler(NOVAException)
# async def nova_exception_handler(request: Request, exc: NOVAException):
#     """
#     处理自定义NOVA异常
#     """
#     logger.error(f"处理NOVA异常: {exc.error_code} - {exc.message}", exc_info=True)
#     return JSONResponse(status_code=exc.status_code, content=create_error_response(exc))


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
