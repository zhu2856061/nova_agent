import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from nova.node import context_summarize, webpage_summarize

input = {
    "messages": [
        {
            "type": "human",
            "content": "帮忙开发客服系统, 千珏 职业赛场使用率 数据分析",
        },
        {
            "type": "human",
            "content": "使用skills 告诉我langgraph是什么?",
        },
        {
            "type": "human",
            "content": "你先按你的思路，实现一个电竞客服系统， 整体框架搭建，并进行开发",
        },
    ],
}

context = {
    "thread_id": "Nova",
    "model": "deepseek",
}
# 同步调用
result = asyncio.run(webpage_summarize.ainvoke(input, context=context))

print(result)
