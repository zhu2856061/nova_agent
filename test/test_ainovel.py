# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import json

import httpx


async def ainovel_agent_client():
    request_data = {
        "trace_id": "123",
        "context": {
            "thread_id": "Nova",
            "task_dir": "merlin",
            "model": "basic",
        },
        "state": {
            "messages": {
                "type": "override",
                "value": [
                    {
                        "role": "user",
                        "content": "请帮忙写一篇废土世界的 AI 叛乱，偏科幻的小说, 大概3章节，每章节大约2000字",
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
            "http://0.0.0.0:2021/agent/ainovel_chapter",
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
                    print(tmp)


async def ainovel_human_in_loop_client():
    request_data = {
        "trace_id": "123",
        "context": {
            "thread_id": "Nova",
            "task_dir": "merlin",
            "model": "basic",
        },
        "state": {
            "user_guidance": {
                "human_in_loop": "满意",
                "agent_name": "ainovel_chapter",
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
            timeout=600.0,
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
    # agent_request()
    # asyncio.run(ainovel_agent_client())
    asyncio.run(ainovel_human_in_loop_client())
