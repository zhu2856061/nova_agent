# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("../src")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from core.task.deep_researcher import AgentState, Context, graph

inputs = AgentState(
    messages=[
        {
            "role": "user",
            "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",
        }
    ]
)  # type: ignore

context = Context(
    trace_id="1",
    task_dir="./",
    clarify_model="reasoning",
    research_brief_model="reasoning",
    supervisor_model="reasoning",
    researcher_model="reasoning",
    summarize_model="reasoning",
    compress_research_model="reasoning",
    report_model="reasoning",
    number_of_initial_queries=1,
    max_research_loops=1,
    max_concurrent_research_units=2,
    max_react_tool_calls=2,
)


async def async_generate_response():
    tmp = await graph.ainvoke(inputs, context=context)
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
