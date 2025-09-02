import json
import logging
import uuid

import requests
import streamlit as st
from utils import get_img_base64

AGENT_PAGE_INTRODUCTION = "你好，我是 **Nova Agent** 智能助手，有什么可以帮助你的吗？"

LLM_OPTIONS = ["basic", "reasoning", "basic_no_thinking"]

# 后端接口地址
BACKEND_URL = "http://0.0.0.0:2021/task/stream_deepresearcher"  # 需根据实际修改
AVATAR_PATH = "chat.png"

logger = logging.getLogger(__name__)


def get_task_response(llm_dtype: str, messages: list, max_react_tool_calls: int):
    """
    发送请求到后端并获取流式响应

    Args:
        llm_dtype: 模型类型
        messages: 对话历史消息
        temperature: 模型温度参数

    Yields:
        流式返回的响应内容片段
    """
    trace_id = str(uuid.uuid4())
    request_data = {
        "trace_id": trace_id,
        "context": {
            "clarify_model": llm_dtype,
            "research_brief_model": llm_dtype,
            "supervisor_model": llm_dtype,
            "researcher_model": llm_dtype,
            "summarize_model": llm_dtype,
            "compress_research_model": llm_dtype,
            "report_model": llm_dtype,
            "number_of_initial_queries": 1,
            "max_research_loops": 1,
            "max_concurrent_research_units": 2,
            "max_react_tool_calls": max_react_tool_calls,
        },
        "state": {
            "messages": messages,
        },
    }
    try:
        # 发送POST请求并设置stream=True以接收流式响应
        with requests.post(
            BACKEND_URL,
            json=request_data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=600,  # 添加超时设置
        ) as response:
            response.raise_for_status()  # 检查HTTP错误状态码
            _reasoning_content_message_id = ""
            _content_message_id = ""
            # 逐行处理流式响应
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue  # 跳过空行
                try:
                    line = json.loads(line)

                    # 检查后端返回的状态码
                    if line.get("code", 1) != 0:
                        error_msg = f"后端错误: {line.get('message', '未知错误')}(code={line.get('code')})"
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield error_msg
                        return

                    # 提取内容（根据实际后端响应结构调整）
                    _event = line["messages"]["event"]
                    _data = line["messages"]["data"]
                    _node_name = _data["node_name"]
                    _step = _data["step"]
                    _run_id = _data["run_id"]
                    _trace_id = _data["trace_id"]

                    if _event == "on_chain_start":
                        if _node_name == "LangGraph":
                            yield "# 开始任务\n\n"
                        else:
                            yield f"## 执行第{_step}步 \n\n"

                    elif _event == "on_chain_end":
                        if _node_name == "LangGraph":
                            yield "# 任务结束\n\n"
                        else:
                            yield f"## 第{_step}步完成\n\n"

                    elif _event == "on_chat_model_start":
                        yield f"### {_node_name}思考中\n\n"

                    elif _event == "on_chat_model_end":
                        yield f"### {_node_name}思考完成\n\n"

                    elif _event == "on_tool_start":
                        _input = _data["input"]
                        yield (
                            f"### 开始调用工具{_node_name}, 工具的入参是{_input} \n\n"
                        )

                    elif _event == "on_tool_end":
                        _output = _data["output"]
                        yield (
                            f"### 工具{_node_name}执行结束, 工具的出参是{_output}"
                            + "\n\n"
                        )

                    elif _event == "on_chat_model_stream":
                        _output = _data["output"]
                        _message_id = _output["message_id"]
                        _reasoning_content = _output.get("reasoning_content", "")
                        _content = _output.get("content", "")

                        if _reasoning_content:
                            if _message_id != _reasoning_content_message_id:
                                _reasoning_content_message_id = _message_id
                                yield f"#### Think\n\n {_reasoning_content}"
                            else:
                                yield _reasoning_content

                        if _content:
                            if _message_id != _content_message_id:
                                _content_message_id = _message_id
                                yield f"#### Answer\n\n {_reasoning_content}"
                            else:
                                yield _content

                except json.JSONDecodeError:
                    error_msg = f"响应格式错误: 无法解析内容 - {line}"
                    logger.error(f"{error_msg} (trace_id: {trace_id})")
                    yield error_msg
                    return
                except KeyError as e:
                    error_msg = f"响应结构错误: 缺少字段 {str(e)}"
                    logger.error(f"{error_msg} (trace_id: {trace_id})")
                    yield error_msg
                    return

    except requests.exceptions.RequestException as e:
        error_msg = f"请求失败: {str(e)}"
        logger.error(f"{error_msg} (trace_id: {trace_id})")
        yield error_msg
        return
    except Exception as e:
        error_msg = f"处理请求时发生意外错误: {str(e)}"
        logger.error(f"{error_msg} (trace_id: {trace_id})")
        yield error_msg
        return


def clear_agent_history():
    st.session_state.chat_history = [
        {"role": "assistant", "content": AGENT_PAGE_INTRODUCTION}
    ]


def display_agent_history():
    """显示对话历史记录"""
    # 确保会话状态中有聊天历史
    if "chat_history" not in st.session_state:
        clear_agent_history()

    for message in st.session_state["chat_history"]:
        # 处理头像获取可能出现的错误
        try:
            avatar = (
                get_img_base64(AVATAR_PATH) if message["role"] == "assistant" else None
            )
        except Exception as e:
            logger.warning(f"获取头像失败: {e}")
            avatar = None

        with st.chat_message(message["role"], avatar=avatar):
            st.write(message["content"])


def llm_task_page():
    """聊天页面主函数"""
    st.set_page_config(
        page_title="Nova 智能助手",
        page_icon=get_img_base64("nova_chat.png"),
        layout="wide",
    )

    # 初始化会话状态
    if "chat_history" not in st.session_state:
        clear_agent_history()

    # 侧边栏配置
    with st.sidebar:
        st.title("🤖 模型配置")
        llm_type = st.selectbox("选择模型", LLM_OPTIONS, index=0)
        max_react_tool_calls = st.slider(
            "执行工具次数",
            min_value=1,
            max_value=5,
            value=2,
            step=1,
        )

    # 显示对话历史
    display_agent_history()

    # 底部输入框
    with st._bottom:
        cols = st.columns([10, 1])
        user_input = cols[0].chat_input("请输入您的问题...")
        if cols[1].button(label=":wastebasket:", help="清空当前对话"):
            clear_agent_history()
            st.rerun()

    # 处理用户输入
    if user_input:
        # 添加用户消息到历史并显示
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        history_messages = st.session_state.chat_history[1:]

        # 获取模型响应并流式显示
        with st.chat_message("assistant", avatar=get_img_base64(AVATAR_PATH)):
            response_generator = get_task_response(
                llm_type, history_messages, max_react_tool_calls
            )
            full_response = st.write_stream(response_generator)

        # 添加助手响应到历史
        st.session_state.chat_history.append(
            {"role": "assistant", "content": full_response}
        )

        # 滚动到底部
        st.rerun()
