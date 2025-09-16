import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from nova.tools.llm_searcher import search_tool

# 同步调用
result = search_tool.invoke(
    {
        "queries": [
            "agent",
            "千珏 职业赛场使用率 数据分析",
        ],
        "max_results": 2,
        "runtime": {"summarize_model": "basic"},
    }
)
