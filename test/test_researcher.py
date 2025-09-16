# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.agent.researcher import researcher_agent

inputs = {
    "researcher_messages": [
        {
            "role": "user",
            "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",
        }
    ],
}
context = {
    "trace_id": 123,
    "researcher_model": "basic",
    "summarize_model": "basic",
    "compress_research_model": "basic",
    "max_react_tool_calls": 2,
}


async def async_generate_response():
    tmp = await researcher_agent.ainvoke(inputs, context=context)  # type: ignore
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
