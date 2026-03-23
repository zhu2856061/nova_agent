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
        "model": "basic",
        "agent": "researcher",
        "models": {"summarize": "basic"},
    },
    "state": {
        "messages": [
            {
                "type": "human",
                "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",  #
            },
        ],
        "data": {"123": "123"},
    },
    "stream": True,
}


async def agent_client():

    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST",
            "http://0.0.0.0:2021/agent/service",
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
                        print(tmp)
                    except Exception:
                        print("==>", tmp)


if __name__ == "__main__":
    asyncio.run(agent_client())
