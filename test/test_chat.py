# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import json

import httpx
import websockets

request_data = {
    "trace_id": "123",
    "context": {"thread_id": "Nova", "model": "deepseek", "agent": "chat"},
    "state": {
        "messages": [
            {
                "type": "human",
                "content": "中国的首都在哪？",  #
            },
        ],
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
                    except Exception:
                        print(tmp)
                    print(tmp)


async def test_agent_websocket():
    token = 1234
    async with websockets.connect(
        f"ws://0.0.0.0:2021/agent/ws?token={token}"
    ) as websocket:
        # 发送请求（JSON 字符串）
        await websocket.send(json.dumps(request_data))

        # 接收响应（流式则循环接收）
        print("=== 开始接收响应 ===")
        while True:
            try:
                response_json = await websocket.recv()
                # 解析为字典，便于查看
                response = json.loads(response_json)
                print(f"code: {response['code']} | data: {response['data']}")

                # 流式场景：判断是否完成
                if (
                    response["code"] == 0
                    and response["data"].get("event_info")
                    and response["data"].get("event_name") == "on_chain_end"
                    and response["data"]["event_info"].get("node_name") == "LangGraph"
                ):
                    print("=== 流式响应接收完成 ===")
                    break

            except websockets.exceptions.ConnectionClosed:
                print("连接已关闭")
                break


if __name__ == "__main__":
    # asyncio.run(agent_client())
    asyncio.run(test_agent_websocket())
