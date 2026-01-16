# -*- coding: utf-8 -*-
# @Time   : 2025/11/29 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import time
from functools import wraps
from typing import Any, Awaitable, Callable

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel

from nova.llms import get_llm_by_type
from nova.model.agent import Context, Messages, State
from nova.utils.log_utils import log_error_set_color, log_info_set_color

# ========== 全局 Logger 定义 ==========
logger = logging.getLogger(__name__)


def extract_valid_info(response: BaseMessage):
    if "tool_calls" in response.additional_kwargs:
        response.additional_kwargs.pop("tool_calls")


class AgentHooks:
    """所有统一横切逻辑都集中在这里，方便后续扩展"""

    @staticmethod
    async def before_node(node_name: str, state: State, runtime: Runtime[Context]):
        code = state.code
        err_message = state.err_message
        message = str(state.messages.value[-1])
        data = str(state.data)
        model = runtime.context.model
        config = str(runtime.context.config)
        thread_id = runtime.context.thread_id

        message = f"[ENTER] -> {node_name}: code={code} | err_message={err_message} | message={message}... | data={data}... | model={model} | config={config}..."

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：限流、权限、发送 typing 信号、注入全局上下文等

    @staticmethod
    async def after_node(
        node_name: str,
        state: State,
        runtime: Runtime[Context],
        elapsed: float,
    ):
        code = state.code
        err_message = state.err_message
        message = str(state.messages.value[-1])
        data = str(state.data)
        model = runtime.context.model
        config = str(runtime.context.config)
        thread_id = runtime.context.thread_id

        message = f"[EXIT: {elapsed:.3f}s] <- {node_name}: code={code} | err_message={err_message} | message={message}... | data={data}... | model={model} | config={config}..."

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：埋点、prometheus 指标、审计日志等

    @staticmethod
    async def on_error(runtime: Runtime[Context], node_name: str, exc: Exception):
        thread_id = runtime.context.thread_id
        _err_message = log_error_set_color(thread_id, node_name, exc)
        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": _err_message,
                "messages": Messages(type="end"),
            },
        )
        # 可扩展：统一错误上报、转成 AIMessage 错误回复


# ─── 节点装饰器（自动实现 节点前 + 节点后） ───
def node_with_hooks(
    node_func: Callable,
    node_name: str | None = None,
) -> Callable:
    name = node_name or node_func.__name__

    @wraps(node_func)
    async def wrapped(state: State, runtime: Runtime[Context], **kwargs):
        start = time.perf_counter()
        await AgentHooks.before_node(name, state, runtime)

        try:
            result = await node_func(state, runtime, **kwargs)
            elapsed = time.perf_counter() - start
            await AgentHooks.after_node(name, state, runtime, elapsed)

        except Exception as e:
            result = await AgentHooks.on_error(runtime, name, e)
            # 可以选择返回错误状态，也可以抛出

        return result

    return wrapped
