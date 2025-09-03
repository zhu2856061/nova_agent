# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import json

import httpx


async def stream_task_client():
    # 定义请求数据，符合 LLMRequest 的结构
    request_data = {
        "trace_id": "123",
        "context": {
            "clarify_model": "reasoning",
            "research_brief_model": "reasoning",
            "supervisor_model": "reasoning",
            "researcher_model": "reasoning",
            "summarize_model": "reasoning",
            "compress_research_model": "reasoning",
            "report_model": "reasoning",
            "number_of_initial_queries": 1,
            "max_research_loops": 1,
            "max_concurrent_research_units": 2,
            "max_react_tool_calls": 2,
        },
        "state": {
            "messages": [
                {
                    "role": "user",
                    "content": "请查询网络上的信息，深圳的最近3天内的科技领域经济新闻",
                },
            ],
        },
    }

    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST",
            "http://0.0.0.0:2021/task/stream_deepresearcher",
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
    asyncio.run(stream_task_client())
    # stream_llm_request()
