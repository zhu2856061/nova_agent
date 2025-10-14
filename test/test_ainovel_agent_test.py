# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.agent.ainovel_chapter_draft import ainovel_chapter_agent

inputs = {"word_number": 2000, "current_chapter_id": 1, "number_of_chapters": 6}

context = {
    "trace_id": "1",
    "task_dir": "./",
    "chapter_model": "reasoning",
}


async def async_generate_response():
    tmp = await ainovel_chapter_agent.ainvoke(inputs, context=context)  # type: ignore
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
