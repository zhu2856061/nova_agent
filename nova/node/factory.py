# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
from typing import List

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
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

        os.makedirs(f"{_work_dir}/middle", exist_ok=True)
        if isinstance(response, TodoListOutput):
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
