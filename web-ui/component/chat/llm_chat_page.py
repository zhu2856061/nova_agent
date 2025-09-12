import json
import logging
import uuid

import requests
import streamlit as st

from ..utils import get_img_base64

CHAT_PAGE_INTRODUCTION = "你好，我是 **Nova Chat** 智能助手，有什么可以帮助你的吗？"

LLM_OPTIONS = ["basic", "reasoning", "basic_no_thinking"]
# 后端接口地址
BACKEND_URL = "http://0.0.0.0:2021/chat/stream_llm"  # 需根据实际修改
AVATAR_PATH = "chat.png"
# 流式优化参数
MAX_TOTAL_CHARS = 150000  # 总字符保护限制

logger = logging.getLogger(__name__)


def get_chat_response(llm_dtype: str, messages: list, temperature: float):
    """
    发送请求到后端并获取流式响应

    Args:
        llm_dtype: 模型类型
        messages: 对话历史消息

    Yields:
        流式返回的响应内容片段
    """
    trace_id = str(uuid.uuid4())
    request_data = {
        "trace_id": trace_id,
        "llm_dtype": llm_dtype,
        "messages": messages,
        "config": {"temperature": temperature},
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
            # 逐行处理流式响应
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue  # 跳过空行

                try:
                    line_data = json.loads(line)
                    if line_data.get("code", 1) != 0:
                        error_msg = f"❌ 后端错误: {line_data.get('message', '未知错误')}(code={line_data.get('code')})"
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield {"type": "error", "content": error_msg}
                        return

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
                    error_msg = (
                        f"❌ 响应格式错误: 无法解析内容（前200字符）: {line[:200]}..."
                    )
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


def display_chat_history():
    """显示对话历史记录"""
    # 确保会话状态中有聊天历史
    if "chat_history" not in st.session_state:
        clear_chat_history()

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


def clear_chat_history():
    st.session_state.chat_history = [
        {"role": "assistant", "content": CHAT_PAGE_INTRODUCTION}
    ]


def llm_chat_page():
    """聊天页面主函数"""
    st.set_page_config(
        page_title="Nova 智能助手",
        page_icon=get_img_base64("nova_chat.png"),
        layout="wide",
    )

    # 初始化会话状态
    if "chat_history" not in st.session_state:
        clear_chat_history()

    # 侧边栏配置
    with st.sidebar:
        st.title("🤖 模型配置")
        llm_type = st.selectbox("选择模型", LLM_OPTIONS, index=0)
        temperature = st.slider(
            "模型温度",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="值越高，输出越随机；值越低，输出越确定",
        )
        history_len = st.slider(
            "携带历史消息数",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            help="向后端发送的历史消息数量",
        )
        # st.button("清空对话", on_click=clear_chat_history, type="primary")

    # 显示对话历史
    display_chat_history()

    # 底部输入框
    with st._bottom:
        cols = st.columns([10, 1])
        user_input = cols[0].chat_input("请输入您的问题...")
        if cols[1].button(label=":wastebasket:", help="清空当前对话"):
            clear_chat_history()
            st.rerun()

    # 处理用户输入
    if user_input:
        # 添加用户消息到历史并显示
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 获取历史消息（确保不超出范围）
        start_idx = max(0, len(st.session_state.chat_history) - history_len)
        history_messages = st.session_state.chat_history[start_idx:]

        current_answer_message_id = None
        current_reasoning_message_id = None
        # 获取模型响应并流式显示
        with st.chat_message("assistant", avatar=get_img_base64(AVATAR_PATH)):
            sys_container = st.container()  # # 创建容器用于动态展示和折叠
            _temp = ""  # 临时流式内容
            _temp_answer = ""  # 临时流式内容
            _temp_reasoning = ""

            _placeholder = st.empty()  # 用于流式更新的占位符

            full_response = ""  # 控制输出长度的变量

            stream_generator = get_chat_response(
                llm_type, history_messages, temperature
            )

            # 处理流式响应
            for item in stream_generator:
                content = item["content"]
                full_response += str(content)  # 累加完整响应
                if len(full_response) >= MAX_TOTAL_CHARS:
                    full_response += "\n\n⚠️ 已达到最大字符限制，后续内容已截断。"
                    continue  # 终止流式处理
                # 🔹 处理回答内容（流式实时显示）
                elif item["type"] == "answer":
                    _temp_answer += content

                    if not current_answer_message_id:
                        content += "\n\n📘 【Answer】\n\n" + content
                        current_answer_message_id = content
                    # 累加并使用占位符更新（避免闪烁，每1个字符更新一次以实现更平滑的流式效果）
                    _temp += content
                    if _placeholder:
                        _placeholder.markdown(_temp, unsafe_allow_html=False)

                # 🔹 处理思考内容（流式实时显示）
                elif item["type"] == "thought":
                    _temp_reasoning += content
                    if not current_reasoning_message_id:
                        content += "\n\nℹ️ 【Think】\n\n" + content
                        current_reasoning_message_id = content
                    # 累加并使用占位符更新（避免闪烁，每1个字符更新一次以实现更平滑的流式效果）
                    _temp += content
                    if _placeholder:
                        _placeholder.markdown(_temp, unsafe_allow_html=False)

            if _placeholder:
                _placeholder.empty()  # 清空占位符
                _placeholder = None  # 重置占位符
            with sys_container:
                if _temp_reasoning:
                    #  用折叠面板替换，默认不展开
                    with st.expander("查看📝思考过程", expanded=False):
                        st.markdown(
                            _temp_reasoning, unsafe_allow_html=False
                        )  # 包含完成标记

                if _temp_answer:
                    sys_container.markdown(_temp_answer, unsafe_allow_html=False)

        # 添加助手响应到历史
        st.session_state.chat_history.append(
            {"role": "assistant", "content": _temp_answer}
        )

        # 滚动到底部
        # st.rerun()
