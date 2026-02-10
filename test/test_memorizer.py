# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import json

import httpx

request_data = {
    "trace_id": "123",
    "context": {
        "thread_id": "Nova",
        "task_dir": "merlin",
        "model": "basic",
        "config": {"user_id": "merlin"},
    },
    "state": {
        "messages": {
            "type": "override",
            "value": [
                {
                    "role": "user",
                    "content": "Hi, I'm Bob and I enjoy playing tennis. Remember this.",  #
                },
            ],
        },
    },
    "stream": True,
}


async def memorizer_client():
    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST",
            "http://0.0.0.0:2021/agent/memorizer",
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
                    # if tmp["data"]["event"] == "on_chat_model_stream":
                    #     continue
                    print(tmp)


if __name__ == "__main__":
    asyncio.run(memorizer_client())
