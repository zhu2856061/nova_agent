"""

curl -X POST http://0.0.0.0:11021/predict -H 'Content-Type: application/json' -d '{"uid": "123", "businessParam": {"fuid": 139070046, "fage": 21, "fsex": 1, "fcollege_level": 1, "foverdue_max_day": 65, "foverdue_amount": 5028, "fdeduct_strategy_chain_id": 73, "fdeduct_strategy_id": 65}}'

curl -X POST http://mlplatform.fql.com/seldon/mlapp-pre/paytype/predict -H 'Content-Type: application/json' -d '{"uid": "123", "businessParam": {"fuid": 139070046, "fage": 21, "fsex": 1, "fcollege_level": 1, "foverdue_max_day": 65, "foverdue_amount": 5028, "fdeduct_strategy_chain_id": 73, "fdeduct_strategy_id": 65}}'



curl -X GET http://0.0.0.0:12023/health
"""

import asyncio
import json

import httpx


async def stream_llm_client():
    # 定义请求数据，符合 LLMRequest 的结构
    request_data = {
        "trace_id": "12345",
        "llm_dtype": "basic",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "What is the capital of France?",
            },
        ],
    }

    # 使用 httpx 异步客户端发送请求
    async with httpx.AsyncClient() as client:
        # 发送 POST 请求到 /stream_llm 路由
        async with client.stream(
            "POST", "http://0.0.0.0:2021/stream_llm", json=request_data, timeout=20.0
        ) as response:
            # 检查响应状态码
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                return

            async for chunk in response.aiter_bytes():
                if chunk:
                    tmp = json.loads(chunk.decode("utf-8"))
                    print(tmp["messages"]["content"], end="|", flush=True)


asyncio.run(stream_llm_client())
