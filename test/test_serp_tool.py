import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from nova.core.tools.search_engine import serp_tool

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
