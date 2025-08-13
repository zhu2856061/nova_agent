# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("../src")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from core.task.deep_research import Context, State, graph

inputs = State(
    messages=[{"role": "user", "content": "请查询网络上的信息，总结在千珏是什么意思"}]
)
context = Context(
    trace_id="1",
    deep_search_model="basic",
    number_of_initial_queries=1,
    max_research_loops=1,
)


async def async_generate_response():
    tmp = await graph.ainvoke(inputs, context=context)
    print("Assistant:", tmp["messages"][-1].content)


asyncio.run(async_generate_response())
