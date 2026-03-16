# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys

sys.path.append("..")

"""
测试服务LLM是否正常
"""


# def send_chat_request():
#     url = "https://quarkml.oa.fenqile.com/v1/chat/completions"
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": "Bearer lx-ai-1234",
#     }
#     payload = {
#         "model": "Qwen3-235B-A22B",
#         "messages": [{"role": "user", "content": "Hello!"}],
#     }

#     response = requests.post(url, headers=headers, json=payload)
#     response.raise_for_status()  # 如果响应状态码不是200，将抛出HTTPError
#     return response.json()


# # 使用函数
# result = send_chat_request()
# if result:
#     print(result)

# from langchain_core.messages import (
#     AIMessage,
#     AnyMessage,
#     HumanMessage,
#     ToolMessage,
#     get_buffer_string,
# )
# from langgraph.runtime import Runtime

# from nova.model.super_agent import SuperContext, SuperState
# from nova.node.summarize import create_summarize_node

# summa = create_summarize_node()

# x = SuperState(
#     messages=[
#         HumanMessage(
#             "客服是在用户服务体验不完美的情况下，尽可能帮助体验顺畅进行下去的一种解决办法，是问题发生后的一种兜底方案。而智能客服能让大部分简单的问题得以快速自助解决，让复杂问题有机会被人工高效解决。在用户服务的全旅程中，美团平台/搜索与NLP部提供了问题推荐、问题理解、对话管理、答案供给、话术推荐和会话摘要等六大智能客服核心能力，以期达到低成本、高效率、高质量地与用户进行沟通的目的。本文主要介绍了美团智能客服核心技术以及在美团的实践。"
#         )
#     ]
# )
# c = SuperContext(thread_id="xxx", agent="xxx", model="basic")
# runtime = Runtime(context=c)
# tmp = asyncio.run(summa(x, runtime))


# print(tmp)
from langchain_core.messages import HumanMessage

from nova.model.super_agent import SuperContext, SuperState
from nova.node.summarize import summarize

x = SuperState(
    messages=[
        HumanMessage(
            "客服是在用户服务体验不完美的情况下，尽可能帮助体验顺畅进行下去的一种解决办法，是问题发生后的一种兜底方案。而智能客服能让大部分简单的问题得以快速自助解决，让复杂问题有机会被人工高效解决。在用户服务的全旅程中，美团平台/搜索与NLP部提供了问题推荐、问题理解、对话管理、答案供给、话术推荐和会话摘要等六大智能客服核心能力，以期达到低成本、高效率、高质量地与用户进行沟通的目的。本文主要介绍了美团智能客服核心技术以及在美团的实践。"
        )
    ]
)
c = SuperContext(thread_id="xxx", agent="xxx", model="basic")
tmp = asyncio.run(summarize.ainvoke(input=x, context=c))
print(tmp)
