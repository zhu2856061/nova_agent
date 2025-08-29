"""

curl -X GET http://0.0.0.0:2021/health
"""

import requests


def llm_request():
    inputs = {
        "trace_id": "123",
        "llm_dtype": "basic_no_thinking",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "What is the capital of France?",
            },
        ],
    }
    r = requests.post("http://0.0.0.0:2021/chat/llm", json=inputs)
    print(r.json())


if __name__ == "__main__":
    llm_request()
