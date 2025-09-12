# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import logging
import operator
import time
from datetime import datetime
from functools import wraps

from langchain_core.messages import (
    AIMessage,
    MessageLikeRepresentation,
    filter_messages,
)

logger = logging.getLogger(__name__)


# 定义计时装饰器
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()  # 使用高精度计时
        result = func(*args, **kwargs)  # 执行函数
        end_time = time.perf_counter()
        logger.info(f"函数 {func.__name__} 耗时: {end_time - start_time:.4f} 秒")
        return result

    return wrapper


# 设置日志颜色
def set_color(log, color, highlight=True):
    color_set = ["black", "red", "green", "yellow", "blue", "pink", "cyan", "white"]
    try:
        index = color_set.index(color)
    except Exception:
        index = len(color_set) - 1
    prev_log = "\033["
    if highlight:
        prev_log += "1;3"
    else:
        prev_log += "0;3"
    prev_log += str(index) + "m"
    return prev_log + log + "\033[0m"


# 获得当前日期
def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")


# 删除最近一个AI消息
def remove_up_to_last_ai_message(messages: list[MessageLikeRepresentation]):
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            return messages[:i]
    return messages


# 获取笔记
def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    return [
        tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")
    ]


# 筛选消息
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


def handle_event(trace_id, event):
    try:
        kind = event.get("event")
        data = event.get("data")
        name = event.get("name")
        metadata = event.get("metadata", {})
        parent_ids = event.get("parent_ids", [])

        checkpoint_ns = str(metadata.get("checkpoint_ns", ""))
        langgraph_node = str(metadata.get("langgraph_node", ""))
        langgraph_step = str(metadata.get("langgraph_step", ""))

        run_id = str(event.get("run_id", ""))

        if kind == "on_chain_start":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "RunnableSequence" in _name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chain_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                },
            }

            return ydata

        elif kind == "on_chain_end":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "RunnableSequence" in _name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chain_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                },
            }
            return ydata

        elif kind == "on_tool_start":
            _name = langgraph_node + "|" + name

            ydata = {
                "event": "on_tool_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                    "input": data.get("input"),
                },
            }
            return ydata

        elif kind == "on_tool_end":
            _name = langgraph_node + "|" + name

            ydata = {
                "event": "on_tool_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                    "output": data["output"] if data.get("output") else "",
                },
            }
            return ydata

        elif kind == "on_chat_model_start":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chat_model_start",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                },
            }
            return ydata

        elif kind == "on_chat_model_end":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in _name and "tool" in _name:
                return None

            ydata = {
                "event": "on_chat_model_end",
                "data": {
                    "node_name": _name,
                    "step": langgraph_step,
                    "run_id": run_id,
                    "checkpoint_ns": checkpoint_ns,
                    "parent_ids": parent_ids,
                    "trace_id": trace_id,
                    "output": {
                        "content": data["output"].content,
                        "reasoning_content": data["output"].additional_kwargs.get(
                            "reasoning_content", ""
                        ),
                        "tool_calls": data["output"].tool_calls,
                    },
                },
            }
            return ydata

        elif kind == "on_chat_model_stream":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in _name and "tool" in _name:
                return None

            content = data["chunk"].content
            reasoning_content = data["chunk"].additional_kwargs.get("reasoning_content")
            # tool_calls = data["chunk"].additional_kwargs.get("tool_calls")

            if reasoning_content:
                """
                {'chunk': AIMessageChunk(additional_kwargs={'reasoning_content':'Got'}, response_metadata={}, id='run--e09f0e5e-54d2-4c64-87cc-223168efe685')}
                """
                ydata = {
                    "event": "on_chat_model_stream",
                    "data": {
                        "node_name": _name,
                        "step": langgraph_step,
                        "run_id": run_id,
                        "checkpoint_ns": checkpoint_ns,
                        "parent_ids": parent_ids,
                        "trace_id": trace_id,
                        "output": {
                            "message_id": data["chunk"].id,
                            "reasoning_content": data["chunk"].additional_kwargs[
                                "reasoning_content"
                            ],
                        },
                    },
                }

            elif content:
                """
                {'chunk': AIMessageChunk(content='Got', additional_kwargs={}, response_metadata={}, id='run--e09f0e5e-54d2-4c64-87cc-223168efe685')}
                """
                ydata = {
                    "event": "on_chat_model_stream",
                    "data": {
                        "node_name": _name,
                        "step": langgraph_step,
                        "run_id": run_id,
                        "checkpoint_ns": checkpoint_ns,
                        "parent_ids": parent_ids,
                        "trace_id": trace_id,
                        "output": {"message_id": data["chunk"].id, "content": content},
                    },
                }

            else:
                return None

            return ydata

            # elif tool_calls:
            #     """
            #     {'chunk': AIMessageChunk(content='', additional_kwargs={'tool_calls': [ChatCompletionDeltaToolCall(id=None, function=Function(arguments=' introduced', name=None), type='function', index=0)]}, response_metadata={}, id='run--70339d03-adee-4632-b8e8-c9c97f10b164', invalid_tool_calls=[{'name': None, 'args': ' introduced', 'id': None, 'error': None, 'type': 'invalid_tool_call'}], tool_call_chunks=[{'name': None, 'args': ' introduced', 'id': None, 'index': 0, 'type': 'tool_call_chunk'}])}
            #     """
            #     if (
            #         len(tool_calls) > 0
            #         and tool_calls[0].function is not None
            #         and tool_calls[0].function.arguments
            #     ):
            #         ydata = {
            #             "event": "on_chat_model_stream",
            #             "data": {
            #                 "node_name": _name,
            #                 "step": langgraph_step,
            #                 "run_id": run_id,
            #                 "checkpoint_ns": checkpoint_ns,
            #                 "parent_ids": parent_ids,
            #                 "trace_id": trace_id,
            #                 "output": {
            #                     "message_id": data["chunk"].id,
            #                     "tool_calls": tool_calls[0].function.arguments,
            #                 },
            #             },
            #         }

        else:
            return None

    except Exception as e:
        logger.error(f"Error: {e}")
        ydata = {
            "event": "error",
            "data": {
                "node_name": _name,
                "step": langgraph_step,
                "run_id": run_id,
                "trace_id": trace_id,
                "error": str(e),
            },
        }
        return ydata
