# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from langgraph.types import Command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventConfig:
    """事件处理配置常量"""

    # 需要过滤的内部事件关键词（避免展示工具内部执行过程）
    FILTERED_EVENT_KEYWORDS: tuple = (
        ("RunnableSequence", "tool"),
        ("ChatLiteLLMRouter", "tool"),
    )
    # 默认节点名称（当langgraph_node和name都为空时）
    DEFAULT_NODE_NAME: str = "unknown_node"


# ========== 工具函数（复用逻辑） ==========
def should_filter_event(langgraph_node: str, name: str) -> bool:
    """
    判断是否需要过滤当前事件（工具内部执行过程不展示）
    Args:
        langgraph_node: 节点名称
        name: 事件名称
    Returns:
        是否需要过滤
    """
    _name = f"{langgraph_node}|{name}" if langgraph_node else name

    for keyword1, keyword2 in EventConfig.FILTERED_EVENT_KEYWORDS:
        if keyword1 in _name and keyword2 in _name:
            return True
    return False


def get_node_name(langgraph_node: str, name: str) -> str:
    """
    获取标准化的节点名称
    Args:
        langgraph_node: langgraph节点名
        name: 事件名称
    Returns:
        标准化节点名
    """
    node_name = langgraph_node if langgraph_node else name
    return node_name if node_name else EventConfig.DEFAULT_NODE_NAME


def safe_get(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    安全获取嵌套字典的值（避免KeyError/AttributeError）
    Args:
        data: 数据源字典
        path: 取值路径，如 "output.content" 或 "chunk.additional_kwargs.reasoning_content"
        default: 默认值
    Returns:
        获取到的值或默认值
    """
    try:
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value[part]
            else:
                value = getattr(value, part)
        return value if value is not None else default
    except (KeyError, AttributeError, IndexError):
        return default


# ========== 事件处理器映射（策略模式） ==========
class EventHandler:
    """事件处理器基类"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理事件的核心方法"""
        raise NotImplementedError


class ChainStartHandler(EventHandler):
    """处理 on_chain_start 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")

        if should_filter_event(langgraph_node, name):
            return None

        node_name = get_node_name(langgraph_node, name)
        return {
            "event_name": "on_chain_start",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
            },
        }


class ChainEndHandler(EventHandler):
    """处理 on_chain_end 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")

        if should_filter_event(langgraph_node, name):
            return None

        node_name = get_node_name(langgraph_node, name)
        output = safe_get(event, "data.output", "")
        if isinstance(output, Command):
            output = output.update

        return {
            "event_name": "on_chain_end",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
                "output": output,
            },
        }


class ToolStartHandler(EventHandler):
    """处理 on_tool_start 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")
        node_name = get_node_name(langgraph_node, name)

        return {
            "event_name": "on_tool_start",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
                "input": safe_get(event, "data.input", ""),
            },
        }


class ToolEndHandler(EventHandler):
    """处理 on_tool_end 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")
        node_name = get_node_name(langgraph_node, name)

        return {
            "event_name": "on_tool_end",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
                "output": safe_get(event, "data.output", ""),
            },
        }


class ChatModelStartHandler(EventHandler):
    """处理 on_chat_model_start 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")

        if should_filter_event(langgraph_node, name):
            return None

        node_name = get_node_name(langgraph_node, name)
        return {
            "event_name": "on_chat_model_start",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
            },
        }


class ChatModelEndHandler(EventHandler):
    """处理 on_chat_model_end 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")

        if should_filter_event(langgraph_node, name):
            return None

        node_name = get_node_name(langgraph_node, name)
        return {
            "event_name": "on_chat_model_end",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
                "output": {
                    "content": safe_get(event, "data.output.content", ""),
                    "reasoning_content": safe_get(
                        event, "data.output.additional_kwargs.reasoning_content", ""
                    ),
                    "tool_calls": safe_get(event, "data.output.tool_calls", []),
                },
            },
        }


class ChatModelStreamHandler(EventHandler):
    """处理 on_chat_model_stream 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")

        if should_filter_event(langgraph_node, name):
            return None

        node_name = get_node_name(langgraph_node, name)
        chunk = safe_get(event, "data.chunk", {})
        message_id = safe_get(chunk, "id", "")
        reasoning_content = safe_get(chunk, "additional_kwargs.reasoning_content", "")
        content = safe_get(chunk, "content", "")

        if reasoning_content:
            return {
                "event_name": "on_chat_model_stream",
                "event_info": {
                    "trace_id": trace_id,
                    "node_name": node_name,
                    "output": {
                        "message_id": message_id,
                        "reasoning_content": reasoning_content,
                    },
                },
            }
        elif content:
            return {
                "event_name": "on_chat_model_stream",
                "event_info": {
                    "node_name": node_name,
                    "output": {
                        "message_id": message_id,
                        "content": content,
                    },
                },
            }
        return None


class ChainStreamHandler(EventHandler):
    """处理 on_chain_stream 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")
        node_name = get_node_name(langgraph_node, name)

        interrupt_content = safe_get(event, "data.chunk.__interrupt__")
        if interrupt_content:
            return {
                "event_name": "human_in_loop",
                "event_info": {
                    "trace_id": trace_id,
                    "node_name": node_name,
                    "output": safe_get(interrupt_content, "0.value", ""),
                },
            }
        return None


class ParserEndHandler(EventHandler):
    """处理 on_parser_end 事件"""

    @staticmethod
    def handle(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")
        node_name = get_node_name(langgraph_node, name)

        return {
            "event_name": "on_parser_end",
            "event_info": {
                "trace_id": trace_id,
                "node_name": node_name,
                "output": safe_get(event, "data.output", ""),
            },
        }


# ========== 事件处理器映射表 ==========
EVENT_HANDLERS: Dict[str, Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]] = {
    "on_chain_start": ChainStartHandler.handle,
    "on_chain_end": ChainEndHandler.handle,
    "on_tool_start": ToolStartHandler.handle,
    "on_tool_end": ToolEndHandler.handle,
    "on_chat_model_start": ChatModelStartHandler.handle,
    "on_chat_model_end": ChatModelEndHandler.handle,
    "on_chat_model_stream": ChatModelStreamHandler.handle,
    "on_chain_stream": ChainStreamHandler.handle,
    "on_parser_end": ParserEndHandler.handle,
}


# ========== 核心事件处理函数 ==========
def handle_event(trace_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    统一处理LangGraph各类事件，结构化输出事件信息

    Args:
        trace_id: 追踪ID
        event: 原始事件字典

    Returns:
        结构化的事件数据，过滤的事件返回None
    """
    try:
        # 获取事件类型
        event_kind = safe_get(event, "event")

        # 查找对应的处理器
        handler = EVENT_HANDLERS.get(event_kind)
        if not handler:
            return None

        # 执行处理器
        return handler(trace_id, event)

    except Exception as e:
        # 异常处理：保证主流程不崩溃，同时记录详细错误
        logger.error(
            f"Event processing failed (trace_id={trace_id}): {str(e)}", exc_info=True
        )

        # 提取出错时的节点名称（尽可能）
        langgraph_node = safe_get(event, "metadata.langgraph_node", "")
        name = safe_get(event, "name", "")
        _name = get_node_name(langgraph_node, name)

        return {
            "event_name": "error",
            "event_info": {
                "trace_id": trace_id,
                "node_name": _name,
                "output": str(e),
            },
        }


# # 事件处理
# def handle_event(trace_id, event):
#     try:
#         kind = event.get("event")
#         data = event.get("data")
#         name = event.get("name")
#         metadata = event.get("metadata", {})

#         langgraph_node = str(metadata.get("langgraph_node", ""))

#         # parent_ids = event.get("parent_ids", [])
#         # checkpoint_ns = str(metadata.get("checkpoint_ns", ""))
#         # langgraph_step = str(metadata.get("langgraph_step", ""))
#         # run_id = str(event.get("run_id", ""))

#         if kind == "on_chain_start":
#             _name = langgraph_node + "|" + name
#             # 工具内部执行过程不再展示
#             if "RunnableSequence" in _name and "tool" in _name:
#                 return None
#             node_name = name if langgraph_node == "" else langgraph_node
#             ydata = {
#                 "event_name": "on_chain_start",
#                 "event_info": {
#                     "node_name": node_name,
#                     "trace_id": trace_id,
#                 },
#             }

#             return ydata

#         elif kind == "on_chain_end":
#             _name = langgraph_node + "|" + name
#             # 工具内部执行过程不再展示
#             if "RunnableSequence" in _name and "tool" in _name:
#                 return None
#             output = data["output"] if data.get("output") else ""
#             if isinstance(output, Command):
#                 output = output.update
#             node_name = name if langgraph_node == "" else langgraph_node
#             ydata = {
#                 "event_name": "on_chain_end",
#                 "event_info": {
#                     "node_name": node_name,
#                     "output": output,
#                 },
#             }
#             return ydata

#         elif kind == "on_tool_start":
#             node_name = name if langgraph_node == "" else langgraph_node

#             ydata = {
#                 "event_name": "on_tool_start",
#                 "event_info": {
#                     "node_name": node_name,
#                     "input": data["input"] if data.get("input") else "",
#                 },
#             }
#             return ydata

#         elif kind == "on_tool_end":
#             node_name = name if langgraph_node == "" else langgraph_node

#             ydata = {
#                 "event_name": "on_tool_end",
#                 "event_info": {
#                     "node_name": node_name,
#                     "output": data["output"] if data.get("output") else "",
#                 },
#             }
#             return ydata

#         elif kind == "on_chat_model_start":
#             _name = langgraph_node + "|" + name
#             # 工具内部执行过程不再展示
#             if "ChatLiteLLMRouter" in name and "tool" in _name:
#                 return None

#             node_name = name if langgraph_node == "" else langgraph_node
#             ydata = {
#                 "event_name": "on_chat_model_start",
#                 "event_info": {
#                     "node_name": node_name,
#                     "trace_id": trace_id,
#                 },
#             }
#             return ydata

#         elif kind == "on_chat_model_end":
#             _name = langgraph_node + "|" + name
#             # 工具内部执行过程不再展示
#             if "ChatLiteLLMRouter" in _name and "tool" in _name:
#                 return None

#             node_name = name if langgraph_node == "" else langgraph_node
#             ydata = {
#                 "event_name": "on_chat_model_end",
#                 "event_info": {
#                     "node_name": node_name,
#                     "output": {
#                         "content": data["output"].content,
#                         "reasoning_content": data["output"].additional_kwargs.get(
#                             "reasoning_content", ""
#                         ),
#                         "tool_calls": data["output"].tool_calls,
#                     },
#                 },
#             }
#             return ydata

#         elif kind == "on_chat_model_stream":
#             _name = langgraph_node + "|" + name
#             # 工具内部执行过程不再展示
#             if "ChatLiteLLMRouter" in _name and "tool" in _name:
#                 return None

#             node_name = name if langgraph_node == "" else langgraph_node

#             content = data["chunk"].content
#             reasoning_content = data["chunk"].additional_kwargs.get("reasoning_content")
#             # tool_calls = data["chunk"].additional_kwargs.get("tool_calls")

#             if reasoning_content:
#                 """
#                 {'chunk': AIMessageChunk(additional_kwargs={'reasoning_content':'Got'}, response_metadata={}, id='run--e09f0e5e-54d2-4c64-87cc-223168efe685')}
#                 """
#                 ydata = {
#                     "event_name": "on_chat_model_stream",
#                     "event_info": {
#                         "node_name": node_name,
#                         "output": {
#                             "message_id": data["chunk"].id,
#                             "reasoning_content": data["chunk"].additional_kwargs[
#                                 "reasoning_content"
#                             ],
#                         },
#                     },
#                 }

#             elif content:
#                 """
#                 {'chunk': AIMessageChunk(content='Got', additional_kwargs={}, response_metadata={}, id='run--e09f0e5e-54d2-4c64-87cc-223168efe685')}
#                 """
#                 ydata = {
#                     "event_name": "on_chat_model_stream",
#                     "event_info": {
#                         "node_name": node_name,
#                         "output": {"message_id": data["chunk"].id, "content": content},
#                     },
#                 }

#             else:
#                 return None

#             return ydata

#         elif kind == "on_chain_stream":
#             node_name = name if langgraph_node == "" else langgraph_node
#             try:
#                 interrupt_content = data["chunk"].get("__interrupt__")
#             except Exception:
#                 interrupt_content = None

#             if interrupt_content:
#                 ydata = {
#                     "event_name": "human_in_loop",
#                     "event_info": {
#                         "node_name": node_name,
#                         "output": interrupt_content[0].value,
#                     },
#                 }
#                 return ydata

#         elif kind == "on_parser_end":
#             node_name = name if langgraph_node == "" else langgraph_node
#             ydata = {
#                 "event_name": "on_parser_end",
#                 "event_info": {
#                     "node_name": node_name,
#                     "output": data["output"],
#                 },
#             }

#         else:
#             return None

#     except Exception as e:
#         logger.error(
#             f"Event processing failed (trace_id={trace_id}): {str(e)}", exc_info=True
#         )
#         ydata = {
#             "event_name": "error",
#             "event_info": {
#                 "node_name": _name,
#                 "output": str(e),
#             },
#         }
#         return ydata
