# -*- coding: utf-8 -*-
# @Time   : 2025/11/29 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from langchain_core.messages import BaseMessage
from langgraph.errors import GraphInterrupt
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite

from nova.model.config import AgentNodeHooksConfig
from nova.model.super_agent import SuperContext, SuperState
from nova.utils.log_utils import log_error_set_color, log_info_set_color

# ========== 全局 Logger 定义 ==========
logger = logging.getLogger(__name__)


class SuperAgentHooks:
    """所有统一横切逻辑都集中在这里，方便后续扩展"""

    def __init__(self, hook_config: AgentNodeHooksConfig):
        self.hook_config = hook_config

    def truncate_text(self, text: Any) -> str:
        """
        截断文本（支持任意类型转字符串后截断）
        Args:
            text: 要截断的内容（任意类型）
            max_length: 最大长度
        Returns:
            截断后的字符串
        """
        max_length = self.hook_config.truncate_max_length or 1024
        text_str = str(text)
        if len(text_str) <= max_length:
            return text_str
        return f"{text_str[:max_length]}..."

    async def before_node(
        self, node_name: str, state: SuperState, runtime: Runtime[SuperContext]
    ):
        code = state.get("code", 0)
        err_message = state.get("err_message", "ok")
        message = state.get("messages", [])
        data = self.truncate_text(str(state.get("data", {})))
        thread_id = runtime.context.get("thread_id", "default")
        # 截断数据
        message = (
            self.truncate_text(str(message[-1]))
            if message and len(message) > 0
            else self.truncate_text(data)
        )

        message = f"[ENTER] -> {node_name}: code={code} | err_message={err_message} | message={message}... "

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：限流、权限、发送 typing 信号、注入全局上下文等

    async def after_node(
        self,
        node_name: str,
        state: SuperState,
        runtime: Runtime[SuperContext],
        result,
        elapsed: float,
    ):
        thread_id = runtime.context.get("thread_id", "default")
        message = f"[EXIT: {elapsed:.3f}s] <- {node_name}: result: {result}..."

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：埋点、prometheus 指标、审计日志等

    async def on_error(
        self,
        node_name: str,
        state: SuperState,
        runtime: Runtime[SuperContext],
        exc: Exception,
    ):
        thread_id = runtime.context.get("thread_id", "default")
        _err_message = log_error_set_color(thread_id, node_name, exc)

        return Command(
            goto="__end__",
            update={
                "code": 1,
                "err_message": _err_message,
                "messages": Overwrite(
                    [
                        {
                            "role": "assistant",
                            "content": f"error: {_err_message}",  #
                        }
                    ]
                ),
            },
        )
        # 可扩展：统一错误上报、转成 AIMessage 错误回复

    # ─── 节点装饰器（自动实现 节点前 + 节点后） ───
    def node_with_hooks(self, node_name: Optional[str] = None) -> Callable:
        """节点装饰器（封装前置/后置/异常处理逻辑）
        用法：
            @agent_hooks.node_with_hooks(node_name="my_node")
            async def my_node(state: SuperState, runtime: Runtime[SuperContext]):
                ...
        Args:
            node_name: 自定义节点名称（默认使用函数名）

        Returns:
            装饰器函数
        """

        def decorator(node_func: Callable) -> Callable:
            # 确定节点名称
            func_name = node_name or node_func.__name__

            @wraps(node_func)
            async def wrapped(
                state: SuperState, runtime: Runtime[SuperContext], **kwargs
            ):
                try:
                    start_time = (
                        time.perf_counter() if self.hook_config.enable_timing else 0.0
                    )

                    # 执行前置钩子
                    await self.before_node(func_name, state, runtime)

                    # 执行原节点函数
                    result = await node_func(state, runtime, **kwargs)

                    # 计算耗时并执行后置钩子
                    elapsed = (
                        time.perf_counter() - start_time
                        if self.hook_config.enable_timing
                        else 0.0
                    )
                    await self.after_node(func_name, state, runtime, result, elapsed)

                    return result
                except GraphInterrupt as e:
                    # 可选：记录一条特殊的日志，表示节点进入等待人工干预状态
                    thread_id = runtime.context.get("thread_id", "default")
                    log_info_set_color(
                        thread_id,
                        func_name,
                        f"[SUSPENDED] -> Waiting for human input... {e}",
                    )
                    raise
                    # return extract_interrupt_data_from_exc(e)  # type: ignore
                except Exception as e:
                    # 执行异常钩子
                    return await self.on_error(func_name, state, runtime, e)

            return wrapped

        return decorator

    @staticmethod
    def extract_valid_info(response: BaseMessage):
        if "tool_calls" in response.additional_kwargs:
            response.additional_kwargs.pop("tool_calls")

    # ========== 扩展方法（预留） ==========
    def _check_rate_limit(self, context_data: Dict[str, Any]):
        """限流检查（扩展点）"""
        pass

    def _validate_permission(self, context_data: Dict[str, Any]):
        """权限校验（扩展点）"""
        pass

    def _report_metrics(
        self, node_name: str, elapsed: float, context_data: Dict[str, Any]
    ):
        """性能指标上报（扩展点）"""
        pass

    def _report_error(self, thread_id: str, node_name: str, exc: Exception):
        """错误上报（扩展点）"""
        pass
