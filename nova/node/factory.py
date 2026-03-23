# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
from typing import cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    SystemMessage,
    ToolMessage,
    convert_to_messages,
)
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite

from nova import CONF
from nova.model.super_agent import SuperContext, SuperState
from nova.provider import get_llms_provider, get_prompts_provider, get_super_agent_hooks
from nova.utils.common import truncate_if_too_long

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
_DEFAULT_TRIM_TOKEN_LIMIT = 4000
_DEFAULT_FALLBACK_MESSAGE_COUNT = 15


class NodeFactory:
    @staticmethod
    async def create_node(
        node_name,
        *,
        state: SuperState,
        runtime: Runtime[SuperContext],
        is_create_work_dir=False,
        tools=None,
        structured_output=None,
        _before_model_hooks=None,
        _after_model_hooks=None,
    ):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

        # 创建工作目录
        if is_create_work_dir:
            _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
            _work_dir = os.path.join(cast(str, _task_dir), _thread_id)
            os.makedirs(_work_dir, exist_ok=True)
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
        if _before_model_hooks is not None:
            response = await _before_model_hooks(state, runtime)
        else:
            response = _messages
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
        if _after_model_hooks is not None:
            response = await _after_model_hooks(response, state, runtime)
        else:
            response = await NodeFactory.after_model_hooks(response, state, runtime)

        return response

    # 核心：组装提示词
    @staticmethod
    async def before_model_hooks(
        prompt_dir: str,
        prompt_name: str,
        state: SuperState,
        runtime: Runtime[SuperContext],
    ):
        # 当前messages
        _messages = cast(list[AnyMessage], state.get("messages"))

        _system_prompt = get_prompts_provider().get_template(prompt_dir, prompt_name)

        logger.info(f"prompt: {truncate_if_too_long(_system_prompt)}")

        return [
            SystemMessage(content=_system_prompt),
        ] + _messages

    @staticmethod
    async def after_model_hooks(
        response: AIMessage, state: SuperState, runtime: Runtime[SuperContext]
    ):
        _thread_id = runtime.context.get("thread_id", "default")
        logger.info(
            f"_thread_id={_thread_id}, result: {truncate_if_too_long(str(response))}"
        )
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


# 创建节点
def create_node(
    node_name,
    *,
    prompt_dir=None,
    prompt_name=None,
    tools=None,
    structured_output=None,
    is_create_work_dir=False,
):
    _hook = get_super_agent_hooks()

    # 核心：组装提示词
    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 当前messages
        # 当前messages
        _messages = cast(list[AnyMessage], state.get("messages"))

        if not prompt_dir or not prompt_name:
            return _messages

        _system_prompt = get_prompts_provider().get_template(prompt_dir, prompt_name)

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

    @_hook.node_with_hooks(node_name=node_name)
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

        # 创建工作目录
        if is_create_work_dir:
            _task_dir = runtime.context.get("task_dir", CONF.SYSTEM.task_dir)
            _work_dir = os.path.join(cast(str, _task_dir), _thread_id)
            os.makedirs(_work_dir, exist_ok=True)

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
        return await _after_model_hooks(state, runtime, response)

    return _node


def create_patch_tools_node(node_name="patch_tools"):
    """创建补丁工具节点"""
    _hook = get_super_agent_hooks()

    @_hook.node_with_hooks(node_name=node_name)
    async def patch_tools(state: SuperState, runtime: Runtime[SuperContext]):
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

        # 获取状态变量
        _code = state.get("code", 0)
        if _code != 0:
            return Command(goto="__end__")

        _messages = state.get("messages")
        if not _messages:
            return Command(
                update={"code": -1, "data": {"result": "No messages"}},
            )

        if not _messages or len(_messages) == 0:
            return {"code": 1, "err_message": "messages is empty"}

        _messages = convert_to_messages(_messages)
        patched_messages = []
        # Iterate over the messages and add any dangling tool calls
        for i, msg in enumerate(_messages):
            patched_messages.append(msg)
            if msg.type == "ai" and msg.tool_calls:  # type: ignore
                for tool_call in msg.tool_calls:  # type: ignore
                    corresponding_tool_msg = next(
                        (
                            msg
                            for msg in _messages[i:]
                            if msg.type == "tool"
                            and msg.tool_call_id == tool_call["id"]  # type: ignore
                        ),
                        None,
                    )
                    if corresponding_tool_msg is None:
                        # We have a dangling tool call which needs a ToolMessage
                        tool_msg = (
                            f"Tool call {tool_call['name']} with id {tool_call['id']} was "
                            "cancelled - another message came in before it could be completed."
                        )
                        patched_messages.append(
                            ToolMessage(
                                content=tool_msg,
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )
                        logger.info(
                            f"[{node_name}] thread_id:{_thread_id} tool msg: {tool_msg}"
                        )
        return Command(update={"messages": Overwrite(patched_messages)})

    return patch_tools
