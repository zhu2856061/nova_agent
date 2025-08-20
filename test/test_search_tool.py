import sys

sys.path.append("../src")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from core.tools.search_engine import search_tool

# 同步调用
result = search_tool.invoke(
    {
        "queries": [
            "千珏 官方背景故事 Riot Games",
            "千珏 职业赛场使用率 数据分析",
        ],
        "max_results": 2,
        "runtime": {"summarize_model": "longcontext"},
    }
)
