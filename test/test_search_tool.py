import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"


from nova.tools.web_wechat_search import web_search

tool_call = {
    "queries": [
        "agent",
        "千珏 职业赛场使用率 数据分析",
    ],
}
result = asyncio.run(
    web_search.arun(
        tool_input=tool_call,
    )
)
print(result)
