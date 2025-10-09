# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.task.ainovel import ainovel

inputs = {
    "messages": [
        {
            "role": "user",
            "content": "请帮忙写一篇废土世界的 AI 叛乱，偏科幻的小说, 大概3章节，每章节大约2000字",
        }
    ],
}

context = {
    "trace_id": "1",
    "task_dir": "./",
    "clarify_model": "reasoning",
    "architecture_model": "reasoning",
}


async def async_generate_response():
    tmp = await ainovel.ainvoke(inputs, context=context)  # type: ignore
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
