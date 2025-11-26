# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# 事件处理
def handle_event(trace_id, event):
    try:
        kind = event.get("event")
        data = event.get("data")
        name = event.get("name")
        metadata = event.get("metadata", {})

        langgraph_node = str(metadata.get("langgraph_node", ""))

        # parent_ids = event.get("parent_ids", [])
        # checkpoint_ns = str(metadata.get("checkpoint_ns", ""))
        # langgraph_step = str(metadata.get("langgraph_step", ""))
        # run_id = str(event.get("run_id", ""))

        if kind == "on_chain_start":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "RunnableSequence" in _name and "tool" in _name:
                return None
            node_name = name if langgraph_node == "" else langgraph_node
            ydata = {
                "event": "on_chain_start",
                "data": {
                    "node_name": node_name,
                    "trace_id": trace_id,
                },
            }

            return ydata

        elif kind == "on_chain_end":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "RunnableSequence" in _name and "tool" in _name:
                return None

            node_name = name if langgraph_node == "" else langgraph_node
            ydata = {
                "event": "on_chain_end",
                "data": {
                    "node_name": node_name,
                    "output": data["output"] if data.get("output") else "",
                },
            }
            return ydata

        elif kind == "on_tool_start":
            node_name = name if langgraph_node == "" else langgraph_node

            ydata = {
                "event": "on_tool_start",
                "data": {
                    "node_name": node_name,
                    # "step": langgraph_step,
                    # "run_id": run_id,
                    # "checkpoint_ns": checkpoint_ns,
                    # "parent_ids": parent_ids,
                    # "trace_id": trace_id,
                    "input": data["input"] if data.get("input") else "",
                },
            }
            return ydata

        elif kind == "on_tool_end":
            node_name = name if langgraph_node == "" else langgraph_node

            ydata = {
                "event": "on_tool_end",
                "data": {
                    "node_name": node_name,
                    # "step": langgraph_step,
                    # "run_id": run_id,
                    # "checkpoint_ns": checkpoint_ns,
                    # "parent_ids": parent_ids,
                    # "trace_id": trace_id,
                    "output": data["output"] if data.get("output") else "",
                },
            }
            return ydata

        elif kind == "on_chat_model_start":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in name and "tool" in _name:
                return None

            node_name = name if langgraph_node == "" else langgraph_node
            ydata = {
                "event": "on_chat_model_start",
                "data": {
                    "node_name": node_name,
                    # "step": langgraph_step,
                    # "run_id": run_id,
                    # "checkpoint_ns": checkpoint_ns,
                    # "parent_ids": parent_ids,
                    # "trace_id": trace_id,
                },
            }
            return ydata

        elif kind == "on_chat_model_end":
            _name = langgraph_node + "|" + name
            # 工具内部执行过程不再展示
            if "ChatLiteLLMRouter" in _name and "tool" in _name:
                return None

            node_name = name if langgraph_node == "" else langgraph_node
            ydata = {
                "event": "on_chat_model_end",
                "data": {
                    "node_name": node_name,
                    # "step": langgraph_step,
                    # "run_id": run_id,
                    # "checkpoint_ns": checkpoint_ns,
                    # "parent_ids": parent_ids,
                    # "trace_id": trace_id,
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

            node_name = name if langgraph_node == "" else langgraph_node

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
                        "node_name": node_name,
                        # "step": langgraph_step,
                        # "run_id": run_id,
                        # "checkpoint_ns": checkpoint_ns,
                        # "parent_ids": parent_ids,
                        # "trace_id": trace_id,
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
                        "node_name": node_name,
                        # "step": langgraph_step,
                        # "run_id": run_id,
                        # "checkpoint_ns": checkpoint_ns,
                        # "parent_ids": parent_ids,
                        # "trace_id": trace_id,
                        "output": {"message_id": data["chunk"].id, "content": content},
                    },
                }

            else:
                return None

            return ydata

        elif kind == "on_chain_stream":
            node_name = name if langgraph_node == "" else langgraph_node
            try:
                interrupt_content = data["chunk"].get("__interrupt__")
            except Exception:
                interrupt_content = None

            if interrupt_content:
                ydata = {
                    "event": "human_in_loop",
                    "data": {
                        "node_name": node_name,
                        # "step": langgraph_step,
                        # "run_id": run_id,
                        # "checkpoint_ns": checkpoint_ns,
                        # "parent_ids": parent_ids,
                        # "trace_id": trace_id,
                        "output": interrupt_content[0].value,
                    },
                }
                return ydata

        elif kind == "on_parser_end":
            node_name = name if langgraph_node == "" else langgraph_node
            ydata = {
                "event": "on_parser_end",
                "data": {
                    "node_name": node_name,
                    # "step": langgraph_step,
                    # "run_id": run_id,
                    # "checkpoint_ns": checkpoint_ns,
                    # "parent_ids": parent_ids,
                    # "trace_id": trace_id,
                    "output": data["output"],
                },
            }

        else:
            return None

    except Exception as e:
        logger.error(f"Error: {e}")
        ydata = {
            "event": "error",
            "data": {
                "node_name": _name,
                # "step": langgraph_step,
                # "run_id": run_id,
                # "trace_id": trace_id,
                "output": str(e),
            },
        }
        return ydata
