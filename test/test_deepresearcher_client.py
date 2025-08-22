# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import requests

inputs = {
    "trace_id": "123",
    "context": {
        "clarify_model": "reasoning",
        "research_brief_model": "reasoning",
        "supervisor_model": "reasoning",
        "researcher_model": "reasoning",
        "summarize_model": "reasoning",
        "compress_research_model": "reasoning",
        "report_model": "reasoning",
        "number_of_initial_queries": 1,
        "max_research_loops": 1,
        "max_concurrent_research_units": 2,
        "max_react_tool_calls": 2,
    },
    "state": {
        "messages": [
            {
                "role": "user",
                "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",
            },
        ],
    },
}
r = requests.post("http://0.0.0.0:2021/task/deep_researcher", json=inputs)
print(r.json())
