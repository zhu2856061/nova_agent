import json
import logging
import uuid

import httpx
import requests

# 后端接口地址
STREAM_AGENT_MEMORIZER_BACKEND_URL = (
    "http://0.0.0.0:2021/agent/memorizer"  # 需根据实际修改
)
STREAM_AGENT_RESEARCHER_BACKEND_URL = (
    "http://0.0.0.0:2021/agent/researcher"  # 需根据实际修改
)
STREAM_AGENT_WECHATRESEARCHER_BACKEND_URL = (
    "http://0.0.0.0:2021/agent/wechat_researcher"  # 需根据实际修改
)
STREAM_AGENT_AINOVEL_ARCHITECT_BACKEND_URL = (
    "http://0.0.0.0:2021/agent/ainovel_architect"  # 需根据实际修改
)
STREAM_AGENT_AINOVEL_CHAPTER_BACKEND_URL = (
    "http://0.0.0.0:2021/agent/ainovel_chapter"  # 需根据实际修改
)

HUMAN_IN_LOOP_BACKEND_URL = "http://0.0.0.0:2021/agent/human_in_loop"

AGENT_AINOVEL_EXTRACT_SETTING_BACKEND_URL = (
    "http://0.0.0.0:2021/agent/ainovel_extract_setting"  # 需根据实际修改
)
logger = logging.getLogger(__name__)


async def get_agent_api(
    url: str,
    trace_id: str,
    state: dict,  # {"memorizer_messages": messages}
    context: dict,
    user_guidance: dict,
    stream=True,
):
    trace_id = trace_id or str(uuid.uuid4())

    request_data = {
        "trace_id": trace_id,
        "context": context,
        "state": state,  # {"memorizer_messages": messages}
        "user_guidance": user_guidance,
        "stream": stream,
    }

    current_answer_message_id = None
    current_reasoning_message_id = None

    try:
        async with httpx.AsyncClient() as client:
            # 发送 POST 请求到 /stream_llm 路由
            async with client.stream(
                "POST", url, json=request_data, timeout=3600.0
            ) as response:
                response.raise_for_status()

                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue

                    try:
                        line_data = json.loads(chunk.decode("utf-8"))

                        if line_data.get("code", 1) != 0:
                            error_msg = f"❌ 后端错误: {line_data.get('message', '未知错误')}(code={line_data.get('code')})"
                            logger.error(f"{error_msg} (trace_id: {trace_id})")
                            yield {"type": "error", "content": error_msg}
                            return

                        _event = line_data["messages"]["event"]
                        _data = line_data["messages"]["data"]
                        _node_name = _data["node_name"]
                        _step = _data["step"] or 0

                        # 系统事件
                        if _event in [
                            "on_chain_start",
                            "on_chain_end",
                            "on_tool_start",
                            "on_tool_end",
                        ]:
                            if _event == "on_chain_start":
                                _graph_name = _node_name.split("|")[0]
                                if "RunnableSequence" in _node_name:
                                    content = None
                                elif "LangGraph" in _node_name:
                                    if _graph_name:
                                        content = f"⏳ 【图{_graph_name}】开始任务\n\n"
                                    else:
                                        content = "⏳ 【图task】开始任务\n\n"
                                else:
                                    content = f"📌 【图{_graph_name}】🚀【第{_step}步执行: {_node_name}】\n\n"

                            elif _event == "on_chain_end":
                                _graph_name = _node_name.split("|")[0]
                                if "RunnableSequence" in _node_name:
                                    content = None
                                elif "LangGraph" in _node_name:
                                    if _graph_name:
                                        content = f"✅ 【图{_graph_name}】 🟢 【任务结束】\n\n"
                                    else:
                                        content = "✅ 【图task】 🟢 【任务结束】\n\n"
                                else:
                                    content = f"⏳ 【图{_graph_name}】🟢【第{_step}步完成】: {_node_name}\n\n"

                            elif _event == "on_tool_start":
                                _input = str(_data["input"])
                                content = (
                                    f"🛠️ 【调用工具: {_node_name}】\n\n入参: {_input[:200]}...\n\n"
                                    if len(_input) > 200
                                    else f"🛠️ 【调用工具: {_node_name}】\n\n入参: {_input}\n\n"
                                )

                            elif _event == "on_tool_end":
                                _output = str(_data["output"])
                                content = (
                                    f"🛠️ 【工具: {_node_name}执行结束】\n\n出参: {_output[:200]}...\n\n"
                                    if len(_output) > 200
                                    else f"🛠️ 【工具: {_node_name}执行结束】\n\n出参: {_output}\n\n"
                                )

                            if content:
                                yield {"type": "system", "content": content}

                        elif _event in [
                            "on_chat_model_start",
                            "on_chat_model_end",
                            "on_chat_model_stream",
                        ]:
                            if _event == "on_chat_model_start":
                                content = f"🤔 【{_node_name}: 正在思考...】\n\n"
                                if content:
                                    yield {"type": "chat_start", "content": content}

                            elif _event == "on_chat_model_end":
                                # title = f"✨ 【{_node_name}: 思考完成】\n\n"
                                reasoning_content = (
                                    _data["output"].get("reasoning_content", "").strip()
                                )
                                content = _data["output"].get("content", "").strip()
                                tool_calls = _data["output"].get("tool_calls", [])

                                key_info = {
                                    "content": content,
                                    "reasoning_content": reasoning_content,
                                    "tool_calls": tool_calls,
                                }

                                yield {"type": "chat_end", "content": key_info}

                            # 模型流式事件 - 区分思考和回答内容
                            elif _event == "on_chat_model_stream":
                                _output = _data["output"]
                                _message_id = _output["message_id"]
                                _reasoning = _output.get("reasoning_content", "")
                                _answer = _output.get("content", "")
                                # _tool_calls = _output.get("tool_calls", [])

                                # 思考内容
                                if _reasoning:
                                    if _message_id != current_reasoning_message_id:
                                        current_reasoning_message_id = _message_id
                                        yield {
                                            "type": "thought",
                                            "content": "\n\n📝 思考过程：\n\n",
                                        }

                                    yield {
                                        "type": "thought",
                                        "content": f"{_reasoning}",
                                    }

                                # 回答内容
                                if _answer:
                                    if _message_id != current_answer_message_id:
                                        current_answer_message_id = _message_id
                                        yield {
                                            "type": "answer",
                                            "content": "\n\n📌 回答内容：\n\n",
                                        }

                                    yield {"type": "answer", "content": f"{_answer}"}

                        elif _event in ["on_chain_stream"]:
                            _output = _data["output"]
                            _content = _output.get("content", "")
                            yield {
                                "type": "human_in_loop",
                                "content": f"\n\n🐞 人工介入：{_content}\n\n",
                            }

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
