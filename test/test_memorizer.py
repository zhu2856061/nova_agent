# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.agent.memorizer import memorizer_agent
from nova.memory import SQLITESTORE

inputs = {
    "memorizer_messages": [
        {
            "role": "user",
            "content": "Hi, I'm Bob and I enjoy playing tennis. Remember this.",
        }
    ],
}

conversation = [
    ["My name is Alice and I love pizza. Remember this."],
    [
        "Hi, I'm Bob and I enjoy playing tennis. Remember this.",
        "Yes, I also have a pet dog named Max.",
        "Max is a golden retriever and he's 5 years old. Please remember this too.",
    ],
    [
        "Hello, I'm Charlie. I work as a software engineer and I'm passionate about AI. Remember this.",
        "I specialize in machine learning algorithms and I'm currently working on a project involving natural language processing.",
        "My main goal is to improve sentiment analysis accuracy in multi-lingual texts. It's challenging but exciting.",
        "We've made some progress using transformer models, but we're still working on handling context and idioms across languages.",
        "Chinese and English have been the most challenging pair so far due to their vast differences in structure and cultural contexts.",
    ],
]

user_id = "merlin"


context = {
    "trace_id": 1234,
    "user_id": user_id,
    "memorizer_model": "basic",
}


# async def async_generate_response():
#     for content in conversation:
#         await memorizer_agent.ainvoke(
#             {
#                 "memorizer_messages": [
#                     {
#                         "role": "user",
#                         "content": content[0],
#                     }
#                 ]
#             },
#             context=context,
#         )

#     namespace = ("memories", user_id)
#     memories = SQLITESTORE.search(namespace)

#     print("Assistant:\n", memories)


# asyncio.run(async_generate_response())


async def async_generate_response():
    tmp = await memorizer_agent.ainvoke(
        inputs,
        context=context,
    )
    print(tmp)

    namespace = ("memories", user_id)
    memories = SQLITESTORE.search(namespace)

    print("Assistant:\n", memories)


asyncio.run(async_generate_response())
