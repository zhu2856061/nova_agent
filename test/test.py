import requests


def send_chat_request():
    url = "https://quarkml.oa.fenqile.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer lx-ai-1234",
    }
    payload = {
        "model": "Qwen3-32B",
        "messages": [{"role": "user", "content": "Hello!"}],
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 如果响应状态码不是200，将抛出HTTPError
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求发生错误: {e}")
        return None


# 使用函数
result = send_chat_request()
if result:
    print(result)
