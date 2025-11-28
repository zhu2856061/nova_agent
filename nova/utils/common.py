# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import operator
import time
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    MessageLikeRepresentation,
    SystemMessage,
    ToolMessage,
    filter_messages,
)
from langgraph.graph.message import (
    BaseMessageChunk,
    # add_messages,
    convert_to_messages,
    message_chunk_to_message,
)  # 关键导入！这是 LangGraph 的内置转换器

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


def override_reducer(current_value: Any, new_value: Any):
    """
    支持两种写入方式：
    - 普通追加：直接返回 BaseMessage 或 List[BaseMessage]
    - 强制覆盖：返回 {"type": "override", "value": [...]}
    """

    if isinstance(new_value, dict) and new_value.get("type") == "override":
        value = new_value.get("value", new_value)
        if not isinstance(value, list):
            value = [value]
        value = [
            message_chunk_to_message(cast(BaseMessageChunk, m))
            for m in convert_to_messages(value)
        ]
        return value
    else:
        if not isinstance(new_value, list):
            new_value = [new_value]
        new_value = [
            message_chunk_to_message(cast(BaseMessageChunk, m))
            for m in convert_to_messages(new_value)
        ]
        value = operator.add(current_value, new_value)
    return value
    # 确保返回的是 List[AnyMessage]，兼容 LangGraph 运行时


# 正向转换：前端raw消息 → Annotated[list[AnyMessage], add_messages]
def raw_to_annotated(
    raw_messages: list[MessageLikeRepresentation],
) -> List[BaseMessage]:
    """
    将前端传来的{"role": ..., "content": ...}列表转换为LangGraph所需的消息列表
    支持所有LangChain消息类型的反向映射
    """
    if not isinstance(raw_messages, list):
        value = [raw_messages]
    value = [
        message_chunk_to_message(cast(BaseMessageChunk, m))
        for m in convert_to_messages(value)
    ]

    return value


# 反向转换：Annotated消息列表 → 前端raw消息（用于响应时序列化）
def annotated_to_raw(annotated_messages: List[AnyMessage]) -> List[Dict]:
    """
    将LangChain消息列表转换为前端可处理的{"role": ..., "content": ...}格式
    覆盖所有可能的消息类型
    """
    raw = []
    for msg in annotated_messages:
        if isinstance(msg, HumanMessage):
            raw.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            raw.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, SystemMessage):
            raw.append({"role": "system", "content": msg.content})
        elif isinstance(msg, FunctionMessage):
            # FunctionMessage需包含name字段
            raw.append({"role": "Function", "name": msg.name, "content": msg.content})
        elif isinstance(msg, ToolMessage):
            raw.append({"role": "Tool", "content": msg.content})
        elif isinstance(msg, ChatMessage):
            # 保留ChatMessage的原始role（如自定义角色）
            raw.append({"role": msg.role, "content": msg.content})
        else:
            # 未知类型默认保留原始信息
            raw.append({"role": "unknown", "content": str(msg.content)})

    return raw
