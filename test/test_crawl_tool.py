import sys

sys.path.append("../src")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from core.tools.search_engine import crawl_tool

# 同步调用
result = crawl_tool.invoke(
    {
        "url": "https://lol.qq.com/data/info-defail.shtml?id=203",
        "keywords": ["千珏"],
    }
)

print(result)
