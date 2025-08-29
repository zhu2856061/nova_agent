"""
curl -X GET http://0.0.0.0:12023/health
"""

import asyncio
import json

import httpx
import requests


def stream_llm_request():
    inputs = {
        "trace_id": "123",
        "llm_dtype": "basic_no_thinking",
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

    try:
        # 发送POST请求并设置stream=True以接收流式响应
        with requests.post(
            "http://0.0.0.0:2021/chat/stream_llm",
            json=inputs,
            stream=True,
            headers={"Accept": "text/event-stream"},
        ) as r:
            r.raise_for_status()  # 检查请求是否成功

            # 逐行处理流式响应
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    try:
                        # 解析JSON数据
                        data = json.loads(line)
                        if data["code"] == 0:
                            print(data["messages"]["content"], end="", flush=True)
                    except json.JSONDecodeError:
                        # 处理非JSON格式的响应
                        print(line, end="", flush=True)

            # 输出完成后换行
            print()

    except requests.exceptions.RequestException as e:
        print(f"请求发生错误: {e}")


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
            "POST",
            "http://0.0.0.0:2021/chat/stream_llm",
            json=request_data,
            timeout=20.0,
        ) as response:
            # 检查响应状态码
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                return

            async for chunk in response.aiter_bytes():
                if chunk:
                    tmp = json.loads(chunk.decode("utf-8"))
                    print(tmp["messages"]["content"], flush=True)


if __name__ == "__main__":
    asyncio.run(stream_llm_client())
    # stream_llm_request()
