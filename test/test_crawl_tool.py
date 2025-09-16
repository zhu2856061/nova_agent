import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from nova.tools.web_crawler import web_crawler_tool

# 同步调用
result = web_crawler_tool.invoke(
    {
        "url": "https://lol.qq.com/data/info-defail.shtml?id=203",
    }
)

print(result)
