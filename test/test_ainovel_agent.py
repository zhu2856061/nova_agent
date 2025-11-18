# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.agent.ainovel_interact import extract_setting_agent

state = {"user_guidance": "写一篇科幻小说"}

context = {
    "trace_id": "1",
    "task_dir": "./",
    "model": "deepseek",
}


async def async_generate_response():
    tmp = await extract_setting_agent.ainvoke(state, context=context)  # type: ignore
    print("Assistant:\n", tmp)


asyncio.run(async_generate_response())
