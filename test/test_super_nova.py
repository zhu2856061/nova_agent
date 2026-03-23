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
        "context": {
            "thread_id": "Nova3",
            "model": "deepseek",
            "agent": chat_router,
            "models": {"summarize": "basic"},
        },
        "state": {
            "messages": [
                {
                    "type": "human",
                    "content": "帮忙编写一个客服系统开发的skill",
                    # "content": "使用skills 告诉我langgraph是什么?",
                    # "content": "你先按你的思路，实现一个电竞客服系统， 整体框架搭建，并进行开发",
                },
            ],
        },
        "stream": True,
    }

    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST",
            "http://0.0.0.0:2021/agent/service",
            json=request_data,
        ) as response:
            # 检查响应状态码
            if response.status_code != 200:
                error_content = await response.aread()
                print(
                    f"Error: 状态码={response.status_code}, 内容={error_content.decode('utf-8')}"
                )
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
            "thread_id": "Nova3",
            "model": "deepseek",
            "models": {"summarize": "basic"},
            "agent": chat_router,
            "is_human_in_loop": True,
        },
        "state": {
            "user_guidance": {
                "human_in_loop": "你自己决定，不懂的话可以上网查",
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
            "http://0.0.0.0:2021/agent/service",
            json=request_data,
        ) as response:
            # 检查响应状态码
            if response.status_code != 200:
                print(f"Error: {response}")
                return

            async for chunk in response.aiter_bytes():
                if chunk:
                    tmp = json.loads(chunk.decode("utf-8"))
                    print(tmp)


if __name__ == "__main__":
    chat_router = "super_nova"
    asyncio.run(agent_client(chat_router))
    # asyncio.run(human_in_loop_client(chat_router))
