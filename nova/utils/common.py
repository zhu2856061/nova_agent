# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import operator
import time
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union, cast

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


def convert_base_message(
    base_msg: BaseMessage,
    target_type=None,  # 可选：手动指定目标类型（优先级高于 type 字段）
) -> Union[
    HumanMessage,
    AIMessage,
    SystemMessage,
    FunctionMessage,
    ToolMessage,
    ChatMessage,
]:
    """
    将 BaseMessage 转换为指定的目标消息类型（根据 type 字段自动匹配，支持手动指定）

    Args:
        base_msg: 待转换的 BaseMessage 实例
        target_type: 可选，手动指定目标类型（如 HumanMessage），优先级高于 base_msg.type

    Returns:
        对应类型的消息实例（HumanMessage/AIMessage 等）

    Raises:
        ValueError: 当 type 字段无效、目标类型不支持，或手动指定的类型与 BaseMessage 类型不匹配时
        AttributeError: 当 BaseMessage 缺少 type 字段时
    """
    # 1. 校验输入：确保 base_msg 是 BaseMessage 实例
    if not isinstance(base_msg, BaseMessage):
        raise ValueError(
            f"输入必须是 BaseMessage 实例，当前类型：{type(base_msg).__name__}"
        )

    # 2. 获取目标类型（手动指定优先，否则从 base_msg.type 自动匹配）
    if target_type is not None:
        # 手动指定时，校验目标类型是否是 BaseMessage 的子类
        if not issubclass(target_type, BaseMessage):
            raise ValueError(
                f"目标类型必须是 BaseMessage 的子类，当前类型：{target_type.__name__}"
            )
    else:
        # 自动匹配：type 字段 -> 目标类型的映射关系
        type_mapping = {
            "human": HumanMessage,
            "ai": AIMessage,
            "system": SystemMessage,
            "function": FunctionMessage,
            "tool": ToolMessage,
            "chat": ChatMessage,
        }
        # 获取 base_msg 的 type 字段（处理可能的缺失）
        msg_type = getattr(base_msg, "type", None)
        if msg_type not in type_mapping:
            raise ValueError(
                f"BaseMessage 的 type 字段无效：{msg_type}。"
                f"支持的 type 值：{list(type_mapping.keys())}"
            )
        target_type = type_mapping[msg_type]

    # 3. 提取 BaseMessage 的核心属性（所有目标类型都兼容的属性）
    common_kwargs = {
        "content": base_msg.content,
        "additional_kwargs": base_msg.additional_kwargs.copy(),  # 浅拷贝避免原对象修改
        "response_metadata": base_msg.response_metadata.copy(),
    }

    # 4. 处理特殊类型的额外必填属性（如 FunctionMessage 需要 name 字段）
    if target_type == FunctionMessage:
        # FunctionMessage 必须包含 name 属性（从 additional_kwargs 提取或报错）
        func_name = common_kwargs["additional_kwargs"].pop("name", None)
        if not func_name:
            raise ValueError(
                "转换为 FunctionMessage 时，BaseMessage 的 additional_kwargs 必须包含 'name' 字段"
            )
        common_kwargs["name"] = func_name

    elif target_type == ChatMessage:
        # ChatMessage 的 role 字段优先使用 base_msg.type，若 additional_kwargs 有则覆盖
        chat_role = common_kwargs["additional_kwargs"].pop("role", base_msg.type)
        common_kwargs["role"] = chat_role

    # 5. 实例化目标类型并返回（过滤目标类型不支持的参数）
    try:
        # 动态创建目标实例，自动过滤不支持的参数（如 BaseMessage 的 type 字段）
        return target_type(**common_kwargs)  # type: ignore
    except TypeError as e:
        raise ValueError(
            f"创建 {target_type.__name__} 实例失败，可能是缺少必填参数或参数不兼容。"
            f"错误详情：{str(e)}"
        ) from e


def extract_ai_message_content(
    ai_message: Union[AIMessage, Dict[str, Any]],
) -> Tuple[Optional[str], Optional[str]]:
    """
    从 AIMessage 对象（或其字典形式）中提取 content 和 reasoning_content

    Args:
        ai_message: LangChain AIMessage 对象 或 其序列化后的字典

    Returns:
        tuple: (content, reasoning_content)
               - 字段存在返回对应字符串，不存在返回 None
    """
    try:
        # ========== 第一步：统一转换为字典（兼容 AIMessage 对象/纯字典） ==========
        if isinstance(ai_message, AIMessage):
            # 从 AIMessage 对象转为字典（保留所有字段）
            msg_dict = ai_message.model_dump()
        elif isinstance(ai_message, dict):
            # 已是字典，直接使用
            msg_dict = ai_message
        else:
            logger.warning(
                f"输入类型错误，仅支持 AIMessage 或 dict，当前类型: {type(ai_message)}"
            )
            return None, None

        # ========== 第二步：提取核心字段 ==========
        # 1. 提取 content（AI回答的核心内容）
        content = msg_dict.get("content")

        # 2. 提取 reasoning_content（思考过程，适配多层嵌套）
        reasoning_content = None
        # 主路径：additional_kwargs → reasoning_content
        if "additional_kwargs" in msg_dict:
            reasoning_content = msg_dict["additional_kwargs"].get("reasoning_content")
            # 兜底路径：additional_kwargs → provider_specific_fields → reasoning_content
            if not reasoning_content:
                reasoning_content = (
                    msg_dict["additional_kwargs"]
                    .get("provider_specific_fields", {})
                    .get("reasoning_content")
                )

        # ========== 第三步：数据清洗 ==========
        # 去除前后空格，空字符串转为 None
        content = (
            content.strip() if isinstance(content, str) and content.strip() else None
        )
        reasoning_content = (
            reasoning_content.strip()
            if isinstance(reasoning_content, str) and reasoning_content.strip()
            else None
        )

        logger.debug(
            f"提取成功：content长度={len(content) if content else 0}, "
            f"reasoning_content长度={len(reasoning_content) if reasoning_content else 0}"
        )
        return content, reasoning_content

    except Exception as e:
        logger.error(f"提取 AIMessage 内容失败: {str(e)}", exc_info=True)
        return None, None
