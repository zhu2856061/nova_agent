# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.agent.wechat_researcher import wechat_researcher_agent

inputs = {
    "wechat_researcher_messages": [
        {
            "role": "user",
            "content": "大模型微调相关的技术报告",
        }
    ],
}

context = {
    "trace_id": 123,
    "wechat_researcher_model": "basic",
    "max_react_tool_calls": 2,
}


async def async_generate_response():
    tmp = await wechat_researcher_agent.ainvoke(inputs, context=context)  # type: ignore
    print("Assistant:\n", tmp["compressed_research"])


asyncio.run(async_generate_response())
