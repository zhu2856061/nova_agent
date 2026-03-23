# -*- coding: utf-8 -*-
# @Time   : 2026/03/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova.model.super_agent import SuperContext, SuperState
from nova.provider import get_llms_provider, get_prompts_provider, get_super_agent_hooks
from nova.utils.common import truncate_if_too_long
from nova.utils.log_utils import log_info_set_color

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 创建节点: 对搜索出的网页内容进行总结， 目的是缩小上下文的长度，防止token溢出
def create_webpage_summarize_node(
    node_name="webpage_summarize", *, tools=None, structured_output=None
):
    """对上下文进行总结， 目的是缩小上下文的长度，防止token溢出"""
    _hook = get_super_agent_hooks()

    async def _before_model_hooks(context):
        # 核心：组装提示词
        _prompt = get_prompts_provider().prompt_apply_template(
            get_prompts_provider().get_template("node", "webpage_summarize"),
            {
                "messages": context,
            },
        )

        return [HumanMessage(content=_prompt)]

    async def _after_model_hooks(
        response: AIMessage, state: SuperState, runtime: Runtime[SuperContext]
    ):

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
            update={"data": {"result": response.content}},
        )

    @_hook.node_with_hooks(node_name="webpage_summarize")
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _models = runtime.context.get("models")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

        if _models:
            _model_name = _models.get(node_name) or _model_name

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

        # if isinstance(_messages[-1], ToolMessage):
        #     return Command(
        #         goto="__end__",
        #     )

        _context = _messages[-1].content

        max_retries = 4
        current_retry = 0
        while current_retry <= max_retries:  # 尝试3次, 防止因为上下文过长，导致失败
            try:
                # 模型执行前
                response = await _before_model_hooks(_context)
                # 4 大模型
                response = await get_llms_provider().llm_wrap_hooks(
                    _thread_id,
                    node_name,
                    response,
                    _model_name,
                    tools=tools,
                    structured_output=structured_output,
                    **_config,  # type: ignore
                )
                log_info_set_color(
                    _thread_id, node_name, truncate_if_too_long(response.content)
                )
                return await _after_model_hooks(response, state, runtime)

            except Exception as e:
                token_limit = int(len(_context) * 0.8)
                logger.warning(
                    f"current_retry: {current_retry}, summarize reducing the chars to: {token_limit}, exec: {e}"
                )
                _context = _context[:token_limit]
                current_retry += 1

        # 模型执行后
        return Command(goto="__end__")

    return _node


def compile_webpage_summarize_agent():
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("webpage_summarize", create_webpage_summarize_node())
    _agent.add_edge(START, "webpage_summarize")
    return _agent.compile()
