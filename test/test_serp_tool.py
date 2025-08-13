import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from src.core.tools.crawl import serp_tool

# 同步调用
result = serp_tool.invoke(
    {
        "query": "Crawl4AI",
        "max_results": 30,
    }
)


for line in result:
    print("=======================")
    print(line)
