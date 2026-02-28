# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import sys

sys.path.append("..")
from nova.tools.newsnow_crawler import DataFetcher

"""
测试服务LLM是否正常
"""


# def send_chat_request():
#     url = "https://quarkml.oa.fenqile.com/v1/chat/completions"
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": "Bearer lx-ai-1234",
#     }
#     payload = {
#         "model": "Qwen3-235B-A22B",
#         "messages": [{"role": "user", "content": "Hello!"}],
#     }

#     response = requests.post(url, headers=headers, json=payload)
#     response.raise_for_status()  # 如果响应状态码不是200，将抛出HTTPError
#     return response.json()


# # 使用函数
# result = send_chat_request()
# if result:
#     print(result)


param = {
    "name": "filesystem_glob_tool",
    "args": {
        "pattern": "*",
        "path": "/root/workspace/gitlab/nova_agent/merlin/Nova/",
    },
    "tool_call_id": "call_f956806abfe345ed98ab78c0",
    "id": "call_f956806abfe345ed98ab78c0",
    "type": "tool_call",
}

tmp = DataFetcher().crawl_websites(ids_list=["toutiao", "baidu"])
print(tmp)
