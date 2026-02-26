# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
import uuid
from typing import List, cast

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
from pydantic import BaseModel

from nova import CONF
from nova.hooks import Agent_Hooks_Instance
from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.model.agent import Context, Messages, State, Todo
from nova.tools import read_file_tool, write_file_tool

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量
_DEFAULT_TRIM_TOKEN_LIMIT = 4000
_DEFAULT_FALLBACK_MESSAGE_COUNT = 15


def create_todos_list_node():
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

        _todos = state.todos

        _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():

            _system_instruction = Prompts_Provider_Instance.get_template(
                "node", "todo_list"
            )

            _result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                }
            )

            try:
                _result = json.loads(_result)
            except Exception:
                _result = {}

            todos = _todos or _result

            latest_update = _messages[-1].content  # type: ignore

            user_content = f"""
            ### 当前状态
            - 现有清单: {json.dumps(todos, ensure_ascii=False)}
            - 最新业务进展: {latest_update}
            - 业务数据上下文: {json.dumps(state.data, ensure_ascii=False)}

            请根据上述信息，给出更新后的全量 todo list。
            """

            return [
                SystemMessage(content=_system_instruction),
                HumanMessage(content=user_content),
            ]

        class TodoListOutput(BaseModel):
            new_todos: List[Todo]

        # 4 大模型
        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id,
            _NODE_NAME,
            await _assemble_prompt(),
            _model_name,
            structured_output=TodoListOutput,
        )

        if isinstance(response, TodoListOutput):
            os.makedirs(f"{_work_dir}/middle", exist_ok=True)
            await write_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                    "text": json.dumps(
                        response.model_dump()["new_todos"], ensure_ascii=False
                    ),
                }
            )
        else:
            return {"code": 1, "err_message": f"todos list error: {response}"}

        return {"code": 0, "err_message": "ok", "todos": response}

    return todos_list


def create_patch_tools_node():
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
        return {"code": 0, "err_message": "ok", "messages": patched_messages}

    return patch_tools


def create_summarization_node(trigger: int = -1):
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


def agent_with_todos_skills_tools_node():
    """
    创建一个agent节点, 该agent具备如下功能：
    1. 创建且维护一个todo list
    2. 自身携带一个技能库
    3. 内置一些工具：ls, read_file, write_file, edit_file, glob, and grep 主要是一些文件操作工具
    4. 内置一个摘要总结

    """

    @Agent_Hooks_Instance.node_with_hooks(node_name="skill_metadata")
    async def skill_metadata(state: State, runtime: Runtime[Context]):
        _NODE_NAME = "skill_metadata"

        # 变量
        _thread_id = runtime.context.thread_id
        _task_dir = runtime.context.task_dir or CONF.SYSTEM.task_dir
        _model_name = runtime.context.model
        _messages = (
            state.messages.value
            if isinstance(state.messages, Messages)
            else state.messages
        )

        _todos = state.todos

        _work_dir = os.path.join(_task_dir, _thread_id)
        os.makedirs(_work_dir, exist_ok=True)

        # 提示词
        async def _assemble_prompt():

            _system_instruction = Prompts_Provider_Instance.get_template(
                "node", "todo_list"
            )

            _result = await read_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                }
            )

            try:
                _result = json.loads(_result)
            except Exception:
                _result = {}

            todos = _todos or _result

            latest_update = _messages[-1].content  # type: ignore

            user_content = f"""
            ### 当前状态
            - 现有清单: {json.dumps(todos, ensure_ascii=False)}
            - 最新业务进展: {latest_update}
            - 业务数据上下文: {json.dumps(state.data, ensure_ascii=False)}

            请根据上述信息，给出更新后的全量 todo list。
            """

            return [
                SystemMessage(content=_system_instruction),
                HumanMessage(content=user_content),
            ]

        class TodoListOutput(BaseModel):
            new_todos: List[Todo]

        # 4 大模型
        response = await LLMS_Provider_Instance.llm_wrap_hooks(
            _thread_id,
            _NODE_NAME,
            await _assemble_prompt(),
            _model_name,
            structured_output=TodoListOutput,
        )

        if isinstance(response, TodoListOutput):
            os.makedirs(f"{_work_dir}/middle", exist_ok=True)
            await write_file_tool.arun(
                {
                    "file_path": f"{_work_dir}/middle/{_NODE_NAME}.md",
                    "text": json.dumps(
                        response.model_dump()["new_todos"], ensure_ascii=False
                    ),
                }
            )
        else:
            return {"code": 1, "err_message": f"todos list error: {response}"}

        return {"code": 0, "err_message": "ok", "todos": response}

    return skill_metadata
