# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import json

import httpx

"""
import os
import sys
sys.path.append("..")
os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.embeddings import Embeddings_Instances

embeddings = Embeddings_Instances.embed_query("质检效果")
"""


async def agent_client(chat_router):
    request_data = {
        "trace_id": "123",
        "context": {
            "thread_id": "Nova",
        },
        "state": {
            "data": {
                "input_path": "/root/workspace/gitlab/nova_agent/test/data.csv",
                "output_path": "/root/workspace/gitlab/nova_agent/test",
            },
        },
        "stream": True,
    }
    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST",
            f"http://0.0.0.0:2021/agent/{chat_router}",
            json=request_data,
            timeout=600.0,
        ) as response:
            # 检查响应状态码
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                return

            async for chunk in response.aiter_bytes():
                if chunk:
                    tmp = json.loads(chunk.decode("utf-8"))
                    try:
                        if tmp["data"]["event_name"] == "on_chat_model_stream":
                            continue
                    except Exception:
                        print(tmp)
                    print(tmp)


if __name__ == "__main__":
    _router = "analyze_intent_health"
    asyncio.run(agent_client(_router))
