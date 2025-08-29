# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import requests

inputs = {
    "trace_id": "123",
    "context": {
        "researcher_model": "reasoning",
        "summarize_model": "reasoning",
        "compress_research_model": "reasoning",
        "max_react_tool_calls": 2,
    },
    "state": {
        "researcher_messages": [
            {
                "role": "user",
                "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",
            },
        ],
    },
}
r = requests.post("http://0.0.0.0:2021/agent/researcher", json=inputs)
print(r.json())
