# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langchain_core.messages import (
    AIMessage,
    SystemMessage,
)
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova.hooks import Super_Agent_Hook_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.super_agent import SuperContext, SuperState
from nova.utils.common import truncate_if_too_long

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


# 创建节点
def create_node(
    node_name, *, prompt_dir=None, prompt_name=None, tools=None, structured_output=None
):
    # 核心：组装提示词
    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 当前messages
        _messages = state.get("messages")

        if not prompt_dir or not prompt_name:
            return _messages

        _system_prompt = Prompts_Provider_Instance.get_template(prompt_dir, prompt_name)

        logger.info(f"prompt: {truncate_if_too_long(_system_prompt)}")

        return [
            SystemMessage(content=_system_prompt),
        ] + _messages

    async def _after_model_hooks(
        state: SuperState, runtime: Runtime[SuperContext], response: AIMessage
    ):

        logger.info(f"result: {truncate_if_too_long(str(response))}")
        if not isinstance(response, AIMessage):
            return Command(
                update={
                    "code": 1,
                    "err_message": "response type not AIMessage",
                    "messages": [response],
                },
            )
        # 去掉冗余信息
        response.additional_kwargs = {}
        response.response_metadata = {}

        return Command(
            update={"messages": [response], "data": {"result": response.content}},
        )

    @Super_Agent_Hook_Instance.node_with_hooks(node_name=node_name)
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})
        # 创建工作目录
        # _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
        # _work_dir = os.path.join(cast(str, _task_dir), _thread_id)
        # os.makedirs(_work_dir, exist_ok=True)

        # 获取状态变量
        _code = state.get("code", 0)
        if _code != 0:
            return Command(goto="__end__")

        _messages = state.get("messages")
        if not _messages:
            return Command(
                goto="__end__",
                update={"code": -1, "messages": [AIMessage(content="No messages")]},
            )

        # 模型执行前
        response = await _before_model_hooks(state, runtime)

        # 模型执行中
        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id,
            node_name,
            response,
            _model_name,
            tools=tools,
            structured_output=structured_output,
            **_config,  # type: ignore
        )
        # 模型执行后
        return await _after_model_hooks(state, runtime, response)

    return _node
