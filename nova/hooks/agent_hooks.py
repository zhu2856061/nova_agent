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
from langgraph.types import Command

from nova.model.agent import Context, Messages, State
from nova.model.config import AgentNodeHooksConfig
from nova.utils.log_utils import log_error_set_color, log_info_set_color

# ========== 全局 Logger 定义 ==========
logger = logging.getLogger(__name__)


def extract_interrupt_data_from_exc(e: Exception) -> Dict[str, Any]:
    """
    针对格式 (Interrupt(value={'message_id': 'Nova', ...}, id='xxx'),) 提取数据

    Args:
        e: 捕获到的 GraphInterrupt 异常对象

    Returns:
        dict: 提取出的 message_id/content 等数据（无数据返回空字典）
    """
    try:
        # 步骤1：先获取异常的 args（print(e) 显示的就是 args 内容）
        if not hasattr(e, "args") or len(e.args) == 0:
            logger.warning("GraphInterrupt 异常无 args 数据")
            return {}

        # 步骤2：取 args[0]（Interrupt 对象）
        interrupt_obj = e.args[0]
        if not interrupt_obj:
            logger.warning("Interrupt 对象为空")
            return {}

        # 步骤3：从 Interrupt 对象提取 value 字段（核心数据）
        # 方式1：直接属性访问（优先）
        if hasattr(interrupt_obj, "value") and isinstance(interrupt_obj.value, dict):
            return interrupt_obj.value

        # 方式2：如果是 NamedTuple/元组，尝试按字段名提取
        if isinstance(interrupt_obj, tuple):
            # 遍历 Interrupt 对象的字段，找到 value
            for field in dir(interrupt_obj):
                if field == "value" and isinstance(getattr(interrupt_obj, field), dict):
                    return getattr(interrupt_obj, field)

        # 步骤4：兜底：解析字符串（针对 print(e) 显示的格式）
        exc_str = str(interrupt_obj)
        import re

        # 匹配 { ... } 中的字典内容
        dict_match = re.search(r"value=({.*?})", exc_str, re.DOTALL)
        if dict_match:
            import json

            # 处理单引号转双引号，兼容 JSON 解析
            dict_str = dict_match.group(1).replace("'", '"')
            return json.loads(dict_str)

        logger.warning(f"未从 Interrupt 对象提取到数据：{exc_str}")
        return {}

    except Exception as extract_err:
        logger.error(f"提取 Interrupt 数据失败：{str(extract_err)}", exc_info=True)
        return {}


class AgentHooks:
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
        self, node_name: str, state: State, runtime: Runtime[Context]
    ):
        code = state.code
        err_message = state.err_message
        message = state.messages
        user_guidance = str(state.user_guidance)
        data = self.truncate_text(str(state.data))
        model = runtime.context.model
        config = str(runtime.context.config)
        thread_id = runtime.context.thread_id

        message = (
            self.truncate_text(str(state.messages.value[-1]))
            if message
            else self.truncate_text(user_guidance)
        )

        message = f"[ENTER] -> {node_name}: code={code} | err_message={err_message} | message={message}... | data={data}... | model={model} | config={config}..."

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：限流、权限、发送 typing 信号、注入全局上下文等

    async def after_node(
        self,
        node_name: str,
        state: State,
        runtime: Runtime[Context],
        elapsed: float,
    ):
        code = state.code
        err_message = state.err_message
        message = state.messages
        user_guidance = str(state.user_guidance)
        data = self.truncate_text(str(state.data))
        model = runtime.context.model
        config = str(runtime.context.config)
        thread_id = runtime.context.thread_id

        message = (
            self.truncate_text(str(state.messages.value[-1]))
            if message
            else self.truncate_text(user_guidance)
        )

        message = f"[EXIT: {elapsed:.3f}s] <- {node_name}: code={code} | err_message={err_message} | message={message}... | data={data}... | model={model} | config={config}..."

        log_info_set_color(thread_id, node_name, message)
        # 可扩展：埋点、prometheus 指标、审计日志等

    async def on_error(self, runtime: Runtime[Context], node_name: str, exc: Exception):
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
    def node_with_hooks(self, node_name: Optional[str] = None) -> Callable:
        """
        节点装饰器（封装前置/后置/异常处理逻辑）
        用法：
            @agent_hooks.node_with_hooks(node_name="my_node")
            async def my_node(state: State, runtime: Runtime[Context]):
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
            async def wrapped(state: State, runtime: Runtime[Context], **kwargs):
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
                    await self.after_node(func_name, state, runtime, elapsed)

                    return result
                except GraphInterrupt as e:
                    return extract_interrupt_data_from_exc(e)  # type: ignore
                except Exception as e:
                    # 执行异常钩子
                    return await self.on_error(runtime, func_name, e)

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
