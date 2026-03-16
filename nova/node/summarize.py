# -*- coding: utf-8 -*-
# @Time   : 2026/03/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from typing import cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
    get_buffer_string,
)
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova.model.super_agent import SuperContext, SuperState
from nova.node.factory import NodeFactory
from nova.provider import get_llms_provider, get_prompts_provider, get_super_agent_hooks
from nova.utils.common import truncate_if_too_long

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 创建节点
def create_summarize_node(node_name="summarize", *, tools=None, structured_output=None):
    _hook = get_super_agent_hooks()

    async def _before_model_hooks(
        prompt_dir: str,
        prompt_name: str,
        state: SuperState,
        runtime: Runtime[SuperContext],
    ):
        # 核心：组装提示词
        _messages = cast(list[AnyMessage], state.get("messages"))
        tmp = {
            "messages": get_buffer_string(_messages),
        }
        _prompt = get_prompts_provider().prompt_apply_template(
            get_prompts_provider().get_template(prompt_dir, prompt_name), tmp
        )

        logger.info(f"prompt: {truncate_if_too_long(_prompt)}")
        return [HumanMessage(content=_prompt)]

    @_hook.node_with_hooks(node_name="memorizer")
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

        if isinstance(_messages[-1], ToolMessage):
            return Command(
                goto="__end__",
            )
        # 模型执行前
        response = await _before_model_hooks("node", "summarize", state, runtime)

        # 模型执行中
        response = await get_llms_provider().llm_wrap_hooks(
            _thread_id,
            node_name,
            response,
            _model_name,
            tools=tools,
            structured_output=structured_output,
            **_config,  # type: ignore
        )

        # 模型执行后
        return await NodeFactory.after_model_hooks(response, state, runtime)

    return _node


def compile_summarize_agent():
    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("summarize", create_summarize_node())
    _agent.add_edge(START, "summarize")
    return _agent.compile()


summarize = compile_summarize_agent()
