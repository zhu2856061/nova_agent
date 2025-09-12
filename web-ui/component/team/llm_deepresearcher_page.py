import json
import logging
import uuid
from typing import Any, Dict, Generator

import requests
import streamlit as st

from ..utils import get_img_base64

AGENT_PAGE_INTRODUCTION = "你好，我是 **Nova Agent** 智能助手，有什么可以帮助你的吗？"
LLM_OPTIONS = ["basic", "reasoning", "basic_no_thinking"]
BACKEND_URL = "http://0.0.0.0:2021/task/stream_deepresearcher"
AVATAR_PATH = "chat.png"

# 流式优化参数
MAX_TOTAL_CHARS = 150000  # 总字符保护限制

logger = logging.getLogger(__name__)


def get_task_response(
    llm_dtype: str, messages: list, max_react_tool_calls: int
) -> Generator[Dict[str, Any], None, None]:
    """生成带类型标记的流式响应，区分思考和回答内容"""
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
        "state": {"messages": messages},
    }

    current_answer_message_id = None
    current_reasoning_message_id = None

    try:
        with requests.post(
            BACKEND_URL,
            json=request_data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=3600,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                try:
                    line_data = json.loads(line)

                    if line_data.get("code", 1) != 0:
                        error_msg = f"❌ 后端错误: {line_data.get('message', '未知错误')}(code={line_data.get('code')})"
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield {"type": "error", "content": error_msg}
                        return

                    _event = line_data["messages"]["event"]
                    _data = line_data["messages"]["data"]
                    _node_name = _data["node_name"]
                    _step = _data["step"] or 0
                    # _run_id = _data["run_id"]
                    # _parent_ids = _data["parent_ids"]
                    # _checkpoint_ns = _data["checkpoint_ns"]
                    # _trace_id = _data["trace_id"]

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
                                    content = (
                                        f"✅ 【图{_graph_name}】 🟢 【任务结束】\n\n"
                                    )
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
                                        "content": "📝 思考过程：\n\n",
                                    }

                                yield {"type": "thought", "content": f"{_reasoning}"}

                            # 回答内容
                            if _answer:
                                if _message_id != current_answer_message_id:
                                    current_answer_message_id = _message_id
                                    yield {
                                        "type": "answer",
                                        "content": "📌 回答内容：\n\n",
                                    }

                                yield {"type": "answer", "content": f"{_answer}"}

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


def clear_task_history():
    st.session_state.chat_history = [
        {"role": "assistant", "content": AGENT_PAGE_INTRODUCTION}
    ]


def display_task_history():
    """显示对话历史记录"""
    # 确保会话状态中有聊天历史
    if "chat_history" not in st.session_state:
        clear_task_history()

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


def llm_deepresearcher_page():
    """主页面函数，实现思考过程流式展示后自动折叠"""
    st.set_page_config(
        page_title="Nova 智能助手",
        page_icon=get_img_base64("nova_chat.png"),
        layout="wide",
    )

    # 初始化会话状态
    if "chat_history" not in st.session_state:
        clear_task_history()

    # 侧边栏配置
    with st.sidebar:
        global MAX_TOTAL_CHARS
        st.title("🚀 配置")
        llm_type = st.selectbox("选择模型", LLM_OPTIONS, index=0)
        max_react_tool_calls = st.slider("工具最大调用次数", 1, 5, 2, 1)
        MAX_TOTAL_CHARS = st.slider("最大总字符限制（千）", 50, 300, 150, 10) * 1000

    # 显示历史消息
    display_task_history()

    # 底部输入框
    with st._bottom:
        cols = st.columns([10, 1])
        user_input = cols[0].chat_input("请输入问题...")
        if cols[1].button(":wastebasket:", help="清空对话历史"):
            clear_task_history()
            st.rerun()

    # 处理用户输入
    if user_input:
        # 添加用户消息
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 流式获取并展示助手响应
        with st.chat_message("assistant", avatar=get_img_base64(AVATAR_PATH)):
            # # 创建容器用于动态展示和折叠
            sys_container = st.container()
            _temp = ""  # 临时流式内容
            _placeholder = None  # 用于流式更新的占位符

            full_response = ""  # 控制输出长度的变量
            final_answer = []
            stream_generator = get_task_response(
                llm_type, st.session_state.chat_history[1:], max_react_tool_calls
            )
            # 处理流式响应
            for item in stream_generator:
                content = item["content"]
                full_response += str(content)  # 累加完整响应
                if len(full_response) >= MAX_TOTAL_CHARS:
                    full_response += "\n\n⚠️ 已达到最大字符限制，后续内容已截断。"
                    continue  # 终止流式处理
                # 🔹 处理 System 消息（如任务状态、工具调用）
                if item["type"] in ["system", "error"]:
                    with sys_container:
                        sys_container.markdown(content, unsafe_allow_html=False)
                    if item["type"] == "error":
                        with sys_container:
                            sys_container.markdown(
                                f"<span style='color:red'>{content}</span>",
                                unsafe_allow_html=True,
                            )
                elif item["type"] == "chat_start":
                    with sys_container:
                        sys_container.markdown(content, unsafe_allow_html=False)

                    # 初始化占位符，用于流式更新
                    _placeholder = st.empty()

                elif item["type"] == "chat_end":
                    if _placeholder:
                        _placeholder.empty()  # 清空占位符
                        _placeholder = None  # 重置占位符

                    if isinstance(content, dict):
                        _reasoning_content = content["reasoning_content"]
                        _content = content["content"]
                        _tool_calls = content["tool_calls"]

                        if _reasoning_content:
                            with sys_container:
                                #  用折叠面板替换，默认不展开
                                with st.expander("查看📝思考过程", expanded=False):
                                    st.markdown(
                                        _reasoning_content, unsafe_allow_html=False
                                    )  # 包含完成标记
                        if _tool_calls:
                            with sys_container:
                                #  用折叠面板替换，默认不展开
                                with st.expander("查看📝工具入参", expanded=False):
                                    st.markdown(
                                        _tool_calls, unsafe_allow_html=False
                                    )  # 包含完成标记

                        if _content:
                            final_answer.append(_content)
                            with sys_container:
                                _content = f"📘 【Answer】\n\n{_content}\n\n"
                                sys_container.markdown(
                                    _content, unsafe_allow_html=False
                                )

                # 🔹 处理回答内容（流式实时显示）
                elif item["type"] == "answer":
                    # 累加并使用占位符更新（避免闪烁，每1个字符更新一次以实现更平滑的流式效果）
                    _temp += content
                    if _placeholder:
                        _placeholder.markdown(_temp, unsafe_allow_html=False)

                # 🔹 处理思考内容（流式实时显示）
                elif item["type"] == "thought":
                    # 累加并使用占位符更新（避免闪烁，每1个字符更新一次以实现更平滑的流式效果）
                    _temp += content
                    if _placeholder:
                        _placeholder.markdown(_temp, unsafe_allow_html=False)

        # 添加完整响应到历史
        st.session_state.chat_history.append(
            {"role": "assistant", "content": final_answer[-1]}
        )
        # st.rerun()
