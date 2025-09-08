# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import requests

inputs = {
    "trace_id": "123",
    "context": {
        "user_id": "merlin",
        "memorizer_model": "reasoning",
    },
    "state": {
        "memorizer_messages": [
            {
                "role": "user",
                "content": "Hi, I'm Bob and I enjoy playing tennis. Remember this.",
            },
        ],
    },
}


inputs2 = {
    "trace_id": "123",
    "context": {
        "user_id": "merlin",
        "memorizer_model": "reasoning",
    },
    "state": {
        "memorizer_messages": [
            {
                "role": "user",
                "content": "what is my name?",
            },
        ],
    },
}

r = requests.post("http://0.0.0.0:2021/agent/memorizer", json=inputs2)
print(r.json())
