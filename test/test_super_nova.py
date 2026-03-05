# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import json

import httpx


async def agent_client(chat_router):
    request_data = {
        "trace_id": "123",
        "context": {"thread_id": "Nova", "model": "basic", "recursion_limit": 100},
        "state": {
            "messages": {
                "type": "add",
                "value": [
                    {
                        "role": "user",
                        "content": "帮忙开发客服系统, 千珏 职业赛场使用率 数据分析, 你不要反问我，你任意发挥",  #
                    },
                ],
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


async def human_in_loop_client(chat_router):
    request_data = {
        "trace_id": "123",
        "context": {
            "thread_id": "Nova",
            "model": "basic",
        },
        "state": {
            "user_guidance": {
                "human_in_loop": "同时开发，不需要关联",
                "agent_name": chat_router,
            },
        },
        "stream": True,
    }

    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST",
            "http://0.0.0.0:2021/agent/human_in_loop",
            json=request_data,
        ) as response:
            # 检查响应状态码
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                return

            async for chunk in response.aiter_bytes():
                if chunk:
                    tmp = json.loads(chunk.decode("utf-8"))
                    print(tmp)


if __name__ == "__main__":
    # chat_router = "chat"
    chat_router = "super_nova"
    # asyncio.run(agent_client(chat_router))
    asyncio.run(human_in_loop_client(chat_router))
