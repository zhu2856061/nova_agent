# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
import uuid
from typing import cast

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
    convert_to_messages,
)
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langgraph.graph.message import (
    REMOVE_ALL_MESSAGES,
)
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova import CONF
from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.agent import Context, Messages, State
from nova.skills import Skill_Hooks_Instance
from nova.tools import (
    filesystem_edit_file_tool,
    filesystem_glob_tool,
    filesystem_grep_tool,
    filesystem_ls_tool,
    filesystem_read_file_tool,
    filesystem_write_file_tool,
    write_file_tool,
    write_todos,
)
from nova.utils.common import split_remove_message

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
_DEFAULT_TRIM_TOKEN_LIMIT = 4000
_DEFAULT_FALLBACK_MESSAGE_COUNT = 15


def create_todos_list_node():
    """创建一个todos_list节点"""

    @Agent_Hooks_Instance.node_with_hooks(node_name="todos_list")
    async def todos_list(state: State, runtime: Runtime[Context]):
        _NODE_NAME = "todos_list"

        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
        _model_name = runtime.context.model
        _messages = (
            state.messages.value
            if isinstance(state.messages, Messages)
            else state.messages
        )

        _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():

            _system_instruction = Prompts_Provider_Instance.get_template(
                "node", "todo_list"
            )

            return [
                SystemMessage(content=_system_instruction),
            ] + _messages

        # 4 大模型
        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id,
            _NODE_NAME,
            await _assemble_prompt(),
            _model_name,
            tools=[write_todos],
        )

        tool_calls = response.tool_calls
        if not tool_calls:  # 如果没有工具调用，则正常返回 - 回复结果
            return Command(
                update={"code": 0, "err_message": "ok", "messages": [response]}
            )

        async def execute_tool_safely(tool, args):
            try:
                return await tool.ainvoke(args)
            except Exception as e:
                return f"Error executing tool: {str(e)}"

        tool_message = await execute_tool_safely(write_todos, tool_calls[-1])
        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        await write_file_tool.arun(
            {
                "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                "text": json.dumps(tool_calls[-1]["args"], ensure_ascii=False),
            }
        )

        return tool_message

    return todos_list


def create_patch_tools_node():
    """创建补丁工具节点"""

    @Agent_Hooks_Instance.node_with_hooks(node_name="patch_tools")
    async def patch_tools(state: State, runtime: Runtime[Context]):
        _NODE_NAME = "patch_tools"
        # 变量
        _thread_id = runtime.context.thread_id
        _messages = (
            state.messages.value
            if isinstance(state.messages, Messages)
            else state.messages
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
                            f"[{_NODE_NAME}] thread_id:{_thread_id} tool msg: {tool_msg}"
                        )
        return {
            "code": 0,
            "err_message": "ok",
            "messages": Messages(type="override", value=patched_messages),
        }

    return patch_tools


def create_summarization_node(trigger: int = -1):
    """创建总结节点"""

    def _ensure_message_ids(messages: list[AnyMessage]) -> None:
        """Ensure all messages have unique IDs for the add_messages reducer."""
        for msg in messages:
            if msg.id is None:
                msg.id = str(uuid.uuid4())

    def _should_summarize(total_tokens: int) -> bool:
        if trigger <= 0:
            return False
        if total_tokens >= trigger:
            return True
        return False

    def _find_safe_cutoff_point(messages: list[AnyMessage], cutoff_index: int) -> int:
        """Find a safe cutoff point that doesn't split AI/Tool message pairs.

        If the message at cutoff_index is a ToolMessage, advance until we find
        a non-ToolMessage. This ensures we never cut in the middle of parallel
        tool call responses.
        """
        while cutoff_index < len(messages) and isinstance(
            messages[cutoff_index], ToolMessage
        ):
            cutoff_index += 1
        return cutoff_index

    def _find_token_based_cutoff(messages: list[AnyMessage]) -> int:
        left, right = 0, len(messages)
        cutoff_candidate = len(messages)
        max_iterations = len(messages).bit_length() + 1
        for _ in range(max_iterations):
            if left >= right:
                break

            mid = (left + right) // 2
            if count_tokens_approximately(messages[mid:]) <= trigger:
                cutoff_candidate = mid
                right = mid
            else:
                left = mid + 1

        if cutoff_candidate == len(messages):
            cutoff_candidate = left
        if cutoff_candidate >= len(messages):
            if len(messages) == 1:
                return 0
            cutoff_candidate = len(messages) - 1

        # Advance past any ToolMessages to avoid splitting AI/Tool pairs
        return _find_safe_cutoff_point(messages, cutoff_candidate)

    def _partition_messages(
        conversation_messages: list[AnyMessage],
        cutoff_index: int,
    ) -> tuple[list[AnyMessage], list[AnyMessage]]:
        """Partition messages into those to summarize and those to preserve."""
        messages_to_summarize = conversation_messages[:cutoff_index]
        preserved_messages = conversation_messages[cutoff_index:]

        return messages_to_summarize, preserved_messages

    def _trim_messages_for_summary(messages: list[AnyMessage]) -> list[AnyMessage]:
        """Trim messages to fit within summary generation limits."""
        try:
            return cast(
                "list[AnyMessage]",
                trim_messages(
                    messages,
                    max_tokens=_DEFAULT_TRIM_TOKEN_LIMIT,
                    token_counter=count_tokens_approximately,
                    start_on="human",
                    strategy="last",
                    allow_partial=True,
                    include_system=True,
                ),
            )
        except Exception:  # noqa: BLE001
            return messages[-_DEFAULT_FALLBACK_MESSAGE_COUNT:]

    def _build_new_messages(summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}"
            )
        ]

    @Agent_Hooks_Instance.node_with_hooks(node_name="summarization")
    async def summarization(state: State, runtime: Runtime[Context]):
        _NODE_NAME = "summarization"

        # 变量
        _thread_id = runtime.context.thread_id
        _model_name = runtime.context.model
        _messages = (
            state.messages.value
            if isinstance(state.messages, Messages)
            else state.messages
        )

        _messages = cast(list[AnyMessage], _messages)

        # 确保每个message有id
        _ensure_message_ids(_messages)
        total_tokens = count_tokens_approximately(_messages)
        if not _should_summarize(total_tokens):
            return {"code": 0, "err_message": "ok"}

        cutoff_index = _find_token_based_cutoff(_messages)

        if cutoff_index <= 0:
            return {"code": 0, "err_message": "ok"}

        messages_to_summarize, preserved_messages = _partition_messages(
            _messages, cutoff_index
        )

        # 提示词
        def _assemble_prompt(trimmed_messages):

            _prompt_tamplate = Prompts_Provider_Instance.get_template(
                "node", _NODE_NAME
            )

            return [
                HumanMessage(
                    content=Prompts_Provider_Instance.prompt_apply_template(
                        _prompt_tamplate, {"messages": trimmed_messages}
                    )
                )
            ]

        if not messages_to_summarize:
            return "No previous conversation history."
        trimmed_messages = _trim_messages_for_summary(messages_to_summarize)
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id,
            _NODE_NAME,
            _assemble_prompt(trimmed_messages),
            _model_name,
        )
        response = response.text.strip()

        new_messages = _build_new_messages(response)

        return {
            "code": 0,
            "err_message": "ok",
            # "messages": Messages(
            #     type="override",
            #     value=[
            #         RemoveMessage(id=REMOVE_ALL_MESSAGES),
            #         *new_messages,
            #         *preserved_messages,
            #     ],
            # ),
            "messages": [
                RemoveMessage(
                    id=REMOVE_ALL_MESSAGES
                ),  # 框架处理后清空所有历史消息，实现会话重置。
                *new_messages,
                *preserved_messages,
            ],
        }

    return summarization


def create_agent_with_todos_skills_tools_node(system_prompt_template: str = ""):
    """
    创建一个agent节点, 该agent具备如下功能：
    1. 自身携带一个技能库
    2. 内置一些工具：ls, read_file, write_file, edit_file, glob, and grep 主要是一些文件操作工具
    """
    tools = [
        filesystem_edit_file_tool,
        filesystem_glob_tool,
        filesystem_grep_tool,
        filesystem_ls_tool,
        filesystem_read_file_tool,
        filesystem_write_file_tool,
        write_todos,
    ]

    @Agent_Hooks_Instance.node_with_hooks(node_name="agent_with_skills_tools")
    async def agent_with_skills_tools(state: State, runtime: Runtime[Context]):
        _NODE_NAME = "agent_with_skills_tools"

        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
        _model_name = runtime.context.model
        _messages = (
            state.messages.value
            if isinstance(state.messages, Messages)
            else state.messages
        )
        _messages = split_remove_message(_messages)

        _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        def _assemble_prompt():
            _system_prompt = [system_prompt_template]

            ## todo list
            _system_prompt.append(
                Prompts_Provider_Instance.get_template("node", "todo_list")
            )

            ## 技能
            _system_prompt.append(Skill_Hooks_Instance.get_skill_prompt_template())

            ## 文件系统操作工具
            _system_prompt.append(
                Prompts_Provider_Instance.prompt_apply_template(
                    Prompts_Provider_Instance.get_template("node", "filesystem"),
                    {"base_path": os.path.abspath(_work_dir)},
                )
            )

            _system_prompt = "\n\n".join(_system_prompt)

            return [
                SystemMessage(content=_system_prompt),
            ] + _messages

        # 4 大模型
        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id, _NODE_NAME, _assemble_prompt(), _model_name, tools=tools
        )

        return Command(
            update={"messages": [response]},
        )

    return agent_with_skills_tools, tools
