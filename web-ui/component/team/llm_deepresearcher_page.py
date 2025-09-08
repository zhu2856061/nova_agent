import json
import logging
import uuid
from collections import deque
from typing import Any, Dict, Generator

import requests
import streamlit as st
from utils import get_img_base64

AGENT_PAGE_INTRODUCTION = "你好，我是 **Nova Agent** 智能助手，有什么可以帮助你的吗？"
LLM_OPTIONS = ["basic", "reasoning", "basic_no_thinking"]
BACKEND_URL = "http://0.0.0.0:2021/task/stream_deepresearcher"
AVATAR_PATH = "chat.png"

# 流式优化参数
MAX_TOTAL_CHARS = 150000  # 总字符保护限制

logger = logging.getLogger(__name__)


class Stack:
    def __init__(self):
        self.items = deque()  # 使用双端队列实现栈

    def push(self, item):
        """入栈操作"""
        self.items.append(item)

    def pop(self):
        """出栈操作"""
        if not self.is_empty():
            return self.items.pop()
        else:
            raise IndexError("栈为空，无法出栈")

    def peek(self):
        """查看栈顶元素"""
        if not self.is_empty():
            return self.items[-1]
        else:
            raise IndexError("栈为空，无法查看栈顶元素")

    def is_empty(self):
        """判断栈是否为空"""
        return len(self.items) == 0

    def size(self):
        """返回栈的大小"""
        return len(self.items)


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
    reasoning_complete = False
    answer_complete = False

    try:
        _graph_stack = Stack()

        with requests.post(
            BACKEND_URL,
            json=request_data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=600,
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
                        "on_chat_model_start",
                        "on_chat_model_end",
                    ]:
                        if _event == "on_chain_start":
                            if "LangGraph" in _node_name:
                                try:
                                    _graph_name = _node_name.split("|")[0]
                                    _peek = _graph_stack.peek()
                                    _graph_stack.push(_graph_name)
                                except Exception:
                                    _graph_stack.push("task")

                                _peek = _graph_stack.peek()
                                content = f"⏳ 【图{_peek}】开始任务\n\n"

                            elif "RunnableSequence" in _node_name:
                                content = None

                            else:
                                _peek = _graph_stack.peek()
                                content = f"📌 【图{_peek}】🚀【第{_step}步执行: {_node_name}】\n\n"

                        elif _event == "on_chain_end":
                            _peek = _graph_stack.peek()
                            if "LangGraph" in _node_name:
                                content = f"✅ 【图{_peek}】 🟢 【任务结束】\n\n"
                                _graph_stack.pop()
                            else:
                                content = f"⏳ 【图{_peek}】🟢【第{_step}步完成】: {_node_name}\n\n"

                        elif _event == "on_chat_model_start":
                            content = f"🤔 【{_node_name}: 正在思考...】\n\n"

                        elif _event == "on_chat_model_end":
                            content = f"✨ 【{_node_name}: 思考完成】\n\n"
                            tmp = _data["output"].get("reasoning_content", "").strip()
                            if tmp:
                                content += f"ℹ️ 【Think】\n\n{tmp}\n\n"

                            tmp = _data["output"].get("content", "").strip()
                            if tmp:
                                content += f"📘 【Answer】\n\n{tmp}\n\n"

                            tmp = str(_data["output"].get("tool_calls", ""))
                            if tmp:
                                content += f"🛠️ 【tool_calls】\n\n{tmp}\n\n"

                        if content:
                            yield {"type": "system", "content": content}

                    # 工具事件
                    elif _event in ["on_tool_start", "on_tool_end"]:
                        if _event == "on_tool_start":
                            _input = str(_data["input"])
                            content = (
                                f"🛠️ 【调用工具: {_node_name}】\n\n入参: {_input[:200]}...\n\n"
                                if len(_input) > 200
                                else f"🛠️ 【调用工具: {_node_name}】\n\n入参: {_input}\n\n"
                            )

                        else:
                            _output = str(_data["output"])
                            content = (
                                f"🛠️ 【工具: {_node_name}执行结束】\n\n出参: {_output[:200]}...\n\n"
                                if len(_output) > 200
                                else f"🛠️ 【工具: {_node_name}执行结束】\n\n出参: {_output}\n\n"
                            )

                        yield {"type": "system", "content": content}

                    # 模型流式事件 - 区分思考和回答内容
                    # elif _event == "on_chat_model_stream":
                    #     _output = _data["output"]
                    #     _message_id = _output["message_id"]
                    #     _reasoning = _output.get("reasoning_content", "")
                    #     _answer = _output.get("content", "")

                    #     # 思考内容
                    #     if _reasoning:
                    #         reasoning_complete = True
                    #         if _message_id != current_reasoning_message_id:
                    #             current_reasoning_message_id = _message_id
                    #             yield {
                    #                 "type": "thought_start",
                    #                 "content": "📝 思考过程：\n\n",
                    #             }
                    #         else:
                    #             yield {"type": "thought", "content": f"{_reasoning}"}
                    #     elif reasoning_complete:
                    #         reasoning_complete = False
                    #         yield {"type": "thought_complete", "content": ""}

                    #     # 回答内容
                    #     if _answer:
                    #         answer_complete = True
                    #         if _message_id != current_answer_message_id:
                    #             current_answer_message_id = _message_id
                    #             yield {
                    #                 "type": "answer_start",
                    #                 "content": "📌 回答内容：\n\n",
                    #             }
                    #         else:
                    #             yield {"type": "answer", "content": f"{_answer}"}
                    #     elif answer_complete:
                    #         answer_complete = False
                    #         yield {"type": "answer_complete", "content": ""}

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


def clear_agent_history():
    st.session_state.chat_history = [
        {"role": "assistant", "content": AGENT_PAGE_INTRODUCTION}
    ]


def display_agent_history():
    """显示对话历史，折叠已完成的思考过程"""
    if "chat_history" not in st.session_state:
        clear_agent_history()

    for msg in st.session_state["chat_history"]:
        try:
            avatar = get_img_base64(AVATAR_PATH) if msg["role"] == "assistant" else None
        except Exception as e:
            logger.warning(f"头像加载失败: {e}")
            avatar = None

        with st.chat_message(msg["role"], avatar=avatar):
            # 检查是否是助手消息且包含思考过程
            if msg["role"] == "assistant" and "📝 思考过程：" in msg["content"]:
                # 分割思考和回答部分
                thought_start = msg["content"].find("📝 思考过程：")
                answer_start = msg["content"].find("📌 回答内容：")

                if thought_start != -1 and answer_start != -1:
                    thought_content = msg["content"][thought_start:answer_start]
                    answer_content = msg["content"][answer_start:]

                    # 折叠思考过程，默认不展开
                    with st.expander("查看思考过程", expanded=False):
                        st.markdown(thought_content, unsafe_allow_html=False)
                    st.markdown(answer_content, unsafe_allow_html=False)
                else:
                    st.markdown(msg["content"], unsafe_allow_html=False)
            else:
                st.markdown(msg["content"], unsafe_allow_html=False)


def llm_deepresearcher_page():
    """主页面函数，实现思考过程流式展示后自动折叠"""
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
        global MAX_TOTAL_CHARS
        st.title("🚀 配置")
        llm_type = st.selectbox("选择模型", LLM_OPTIONS, index=0)
        max_react_tool_calls = st.slider("工具最大调用次数", 1, 5, 2, 1)
        MAX_TOTAL_CHARS = st.slider("最大总字符限制（千）", 50, 300, 150, 10) * 1000

    # 显示历史消息
    display_agent_history()

    # 底部输入框
    with st._bottom:
        cols = st.columns([10, 1])
        user_input = cols[0].chat_input("请输入问题...")
        if cols[1].button(":wastebasket:", help="清空对话历史"):
            clear_agent_history()
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
            thought_container = st.container()  # 思考过程容器
            answer_container = st.container()  # 回答内容容器
            temp_thought = ""  # 临时存储思考内容
            temp_answer = ""  # 累加存储完整回答内容
            full_response = ""  # 完整响应内容

            stream_generator = get_task_response(
                llm_type, st.session_state.chat_history[1:], max_react_tool_calls
            )

            # 处理流式响应
            for item in stream_generator:
                content = item["content"]
                full_response += content  # 累加完整响应
                if len(full_response) >= MAX_TOTAL_CHARS:
                    full_response += "\n\n⚠️ 已达到最大字符限制，后续内容已截断。"
                    break  # 终止流式处理
                # 🔹 处理 System 消息（如任务状态、工具调用）
                if item["type"] in ["system", "error"]:
                    with sys_container:
                        sys_container.markdown(content, unsafe_allow_html=False)
                    if item["type"] == "error":
                        with answer_container:
                            sys_container.markdown(
                                f"<span style='color:red'>{content}</span>",
                                unsafe_allow_html=True,
                            )

                # # 处理回答内容
                # elif item["type"] in ["answer_start", "answer"]:
                #     # 累加回答内容
                #     temp_answer += content
                #     with answer_container:
                #         st.markdown(temp_answer, unsafe_allow_html=False)

                # # 🔹 处理思考过程（流式实时显示）
                # elif item["type"] in ["thought_start", "thought"]:
                #     # 在临时容器中实时显示思考过程
                #     temp_thought += content
                #     if len(temp_thought) % 10 == 0 or item["type"] == "thought_start":
                #         with thought_container:
                #             st.markdown(temp_thought, unsafe_allow_html=True)

                # # 思考完成，替换为折叠容器
                # elif item["type"] == "thought_complete":
                #     with thought_container:
                #         st.empty()  # 清空临时展示
                #         # 用折叠面板替换
                #         with st.expander("查看思考过程", expanded=False):
                #             st.markdown(temp_thought, unsafe_allow_html=False)

            # # 确保最终思考过程被折叠
            # if temp_thought:
            #     with thought_container:
            #         st.empty()
            #         with st.expander("查看思考过程", expanded=False):
            #             st.markdown(temp_thought, unsafe_allow_html=False)

        # 添加完整响应到历史
        st.session_state.chat_history.append(
            {"role": "assistant", "content": full_response}
        )
        st.rerun()
