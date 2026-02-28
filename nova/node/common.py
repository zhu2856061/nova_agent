# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
from typing import Any, Dict, Literal, cast

from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    ToolCall,
)
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova import CONF
from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.agent import Context, Messages, State

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


class BasicNode:
    """节点基类, 分三个过程
    1 进入LLM Model 之前，主要是准备好： 提示词
    2 LLM Model 过程
    3 LLM Model 之后，主要是处理： 输出结果
    """

    def __init__(self):
        pass

    async def after_model_hooks(self, response: AIMessage):
        return Command(
            update={"messages": [response]},
        )

    async def before_model_hooks(
        self,
        _messages,
        prompt_dir,
        prompt_name,
        runtime: Runtime[Context],
        _user_guidance=None,
    ):
        _system_instruction = Prompts_Provider_Instance.get_template(
            prompt_dir, prompt_name
        )

        return [
            SystemMessage(content=_system_instruction),
        ] + _messages

    def create_node(self, prompt_dir, node_name, tools=None, structured_output=None):
        @Agent_Hooks_Instance.node_with_hooks(node_name=node_name)
        async def _node(state: State, runtime: Runtime[Context]):
            # 获取运行时变量
            _thread_id = runtime.context.thread_id
            _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
            _model_name = runtime.context.model
            _config = runtime.context.config

            # 获取状态变量
            _user_guidance = state.user_guidance
            _messages = (
                state.messages.value
                if isinstance(state.messages, Messages)
                else state.messages
            )

            # 创建工作目录
            _work_dir = os.path.join(_task_dir, _thread_id)
            os.makedirs(_work_dir, exist_ok=True)

            # before model hooks
            response = await self.before_model_hooks(
                _messages, prompt_dir, node_name, runtime, _user_guidance
            )

            # model process
            response = await LLMS_Provider_Instance.llm_wrap_hooks(
                _thread_id,
                node_name,
                response,
                _model_name,
                tools=tools,
                structured_output=structured_output,
                **_config,
            )

            # after model hooks
            return await self.after_model_hooks(response)

        return _node


def create_route_tools_edges():
    """创建路由逻辑, 主要是路由到工具还是结束"""

    # 4. 定义路由逻辑：判断是否需要调用工具
    def route_edges(state: State, runtime: Runtime[Context]):
        """
        路由规则：
        - 如果最后一条消息包含 tool_calls → 跳转到 tools 节点
        - 否则 → 结束流程
        """
        # 变量
        _thread_id = runtime.context.thread_id
        _messages = (
            state.messages.value
            if isinstance(state.messages, Messages)
            else state.messages
        )
        last_message = cast(AIMessage, _messages[-1])
        # 检查LLM是否生成了工具调用指令
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
            )
            return "tools"

        return "__end__"

    return route_edges


def create_tool_node(self, tools):
    """创建工具节点, 继承自ToolNode,
    因为Messages自定义了，原始的ToolNode无法使用，所以继承重写
    """

    class CustomToolNode(ToolNode):
        def _parse_input(
            self, input: Dict[str, Any]
        ) -> tuple[list[ToolCall], Literal["list", "dict", "tool_calls"]]:
            """
            重写新版 _parse_input 方法（匹配官方签名）：
            1. 识别自定义 Messages（BaseModel），提取 value 字段
            2. 适配不同输入类型（list/dict/BaseModel）
            3. 沿用原生逻辑提取 ToolCall 并返回类型标记
            """
            messages = getattr(input, "messages", [])

            # 步骤 1：统一解析输入，提取 messages 列表
            if isinstance(messages, dict):
                # 输入是字典（如 {"messages": [...]}）
                input_type: Literal["list", "dict", "tool_calls"] = "dict"
            elif isinstance(messages, Messages):
                # 输入是 BaseModel（优先处理你的自定义 Messages）
                messages = messages.value
                input_type = "dict"  # BaseModel 按 dict 类型标记处理
            elif isinstance(messages, list):
                # 输入是原生消息列表
                input_type = "list"
            else:
                messages = []
                input_type = "list"

            # 步骤 3：提取工具调用（沿用原生逻辑：反向查找最后一条含 tool_calls 的 AIMessage）
            tool_calls: list[ToolCall] = []
            # 反向遍历，找到最后一条包含 tool_calls 的 AI 消息
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    tool_calls = msg.tool_calls  # 取最新的工具调用
                    break  # 找到后立即退出，只处理最后一条

            # 步骤 4：返回符合签名的结果（tool_calls 列表 + 输入类型标记）
            return tool_calls, input_type

    return CustomToolNode(tools)
