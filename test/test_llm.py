# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("../src")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

# 设置环境变量
from pydantic import BaseModel

from core.llms import get_llm_by_type, with_structured_output


class AnswerWithJustification(BaseModel):
    """An answer to the user question along with justification for the answer."""

    answer: str
    justification: str


llm_instance = get_llm_by_type("basic")
llm_instance = with_structured_output(llm_instance, AnswerWithJustification)


async def async_generate_response():
    tmp = await llm_instance.ainvoke("what color is the sky?")
    print(tmp)

    async for chunk in llm_instance.astream("what color is the sky?"):
        # print(chunk.response_metadata)
        print(chunk.content, end="|", flush=True)


asyncio.run(async_generate_response())


# try:
#     llm_instance = with_structured_output(llm_instance, AnswerWithJustification)
#     start = time.time()
#     for chunk in llm_instance.stream(
#         "What weighs more a pound of bricks or a pound of feathers"
#     ):
#         print(chunk.content, end="|", flush=True)
#     end = time.time()
#     print(end - start)
#     # print(res)
# except Exception as e:
#     print("An error occurred:", e)
