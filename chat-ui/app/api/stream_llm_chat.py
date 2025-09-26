import json
import logging
import uuid

import httpx
import requests

# 后端接口地址
STREAM_LLM_BACKEND_URL = "http://0.0.0.0:2021/chat/stream_llm"  # 需根据实际修改

logger = logging.getLogger(__name__)


async def get_stream_llm_response(
    trace_id: str, llm_dtype: str, messages: list, config: dict
):
    """
    发送请求到后端并获取流式响应

    Args:
        llm_dtype: 模型类型
        messages: 对话历史消息

    Yields:
        流式返回的响应内容片段
    """

    trace_id = trace_id or str(uuid.uuid4())

    request_data = {
        "trace_id": trace_id,
        "llm_dtype": llm_dtype,
        "messages": messages,
        "config": dict(config),
    }

    try:
        async with httpx.AsyncClient() as client:
            # 发送 POST 请求到 /stream_llm 路由
            async with client.stream(
                "POST", STREAM_LLM_BACKEND_URL, json=request_data, timeout=20.0
            ) as response:
                # 检查响应状态码
                if response.status_code != 200:
                    logger.error(f"Error: {response.status_code}")
                    return

                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue  # 跳过空行
                    try:
                        line_data = json.loads(chunk.decode("utf-8"))
                        # 提取内容（根据实际后端响应结构调整）
                        content = line_data.get("messages", {}).get("content")
                        reasoning_content = line_data.get("messages", {}).get(
                            "reasoning_content"
                        )
                        if reasoning_content:
                            yield {"type": "thought", "content": f"{reasoning_content}"}

                        if content:
                            yield {"type": "answer", "content": content}

                    except json.JSONDecodeError:
                        error_msg = f"❌ 响应格式错误: 无法解析内容（前200字符）: {chunk[:200]}..."
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield {"type": "error", "content": error_msg}
                        return
                    except KeyError as e:
                        error_msg = f"❌ 响应结构错误: 缺少必要字段「{str(e)}」"
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield {"type": "error", "content": error_msg}
                        return

    except requests.exceptions.RequestException as e:
        error_msg = f"❌ 请求失败: {str(e)}（流式连接中断）"
        logger.error(f"{error_msg} (trace_id: {trace_id})")
        yield {"type": "error", "content": error_msg}
        return
    except Exception as e:
        error_msg = f"❌ 流式处理异常: {str(e)}"
        logger.error(f"{error_msg} (trace_id: {trace_id})")
        yield {"type": "error", "content": error_msg}
        return
