# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

# 设置环境变量
from pydantic import BaseModel, Field

from nova.llms import get_llm_by_type, with_structured_output
from nova.utils import repair_json_output


class Summary(BaseModel):
    summary: str = Field(description="A summary of the webpage content.")
    key_excerpts: str = Field(
        description="A list of key excerpts from the webpage content."
    )


class AnswerWithJustification(BaseModel):
    """An answer to the user question along with justification for the answer."""

    answer: str = Field(description="An answer to the user question.")
    justification: str = Field(
        description="A justification for the answer to the user question."
    )


class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )


llm_instance = get_llm_by_type(
    "basic_no_thinking"
)  # .with_structured_output(AnswerWithJustification)
# llm_instance = get_llm_by_type("reasoning")

question = """请查询网络上的信息，深圳的天气"""


async def async_generate_response():
    tmp = await llm_instance.ainvoke(question)
    print(tmp)
    # print(repair_json_output(tmp.content))

    # async for chunk in llm_instance.astream(question):
    #     # print(chunk.response_metadata)
    #     print(chunk.content, end="|", flush=True)


asyncio.run(async_generate_response())
