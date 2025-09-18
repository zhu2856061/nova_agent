# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.agent.theme_slicer import theme_slicer_agent

inputs = {
    "theme_slicer_messages": [
        {
            "role": "user",
            "content": "帮我研究一个关于依沃西单抗在非小细胞肺癌的临床研究的进展。",
        }
    ],
}

context = {"trace_id": 123, "theme_slicer_model": "basic"}


async def async_generate_response():
    tmp = await theme_slicer_agent.ainvoke(inputs, context=context)  # type: ignore
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
