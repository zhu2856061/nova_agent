# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import sys

sys.path.append("..")

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
import sys

sys.path.append("..")

from nova.sandbox.sandbox_provider import get_sandbox_provider

sandbox = get_sandbox_provider().get("local")

tmp = sandbox.execute(
    command="cd /root/workspace/gitlab/nova_agent/test && python testtxt.py"
)
print(tmp)
