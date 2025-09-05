# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.core.task.deepresearcher import deepresearcher

inputs = {
    "messages": [
        {
            "role": "system",
            "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",
        }
    ],
}

context = {
    "trace_id": "1",
    "task_dir": "./",
    "clarify_model": "reasoning",
    "research_brief_model": "reasoning",
    "supervisor_model": "reasoning",
    "researcher_model": "reasoning",
    "summarize_model": "reasoning",
    "compress_research_model": "reasoning",
    "report_model": "reasoning",
    "max_concurrent_research_units": 1,
    "max_react_tool_calls": 1,
}


async def async_generate_response():
    tmp = await deepresearcher.ainvoke(inputs, context=context)  # type: ignore
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
