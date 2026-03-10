# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Annotated, Dict, NotRequired

from langgraph.graph.message import (
    AnyMessage,
    add_messages,
)

# from langgraph.types import Overwrite 很重要
from typing_extensions import TypedDict

"""
使用 Overwrite 绕过 reducer
def add_message(state: State):
    return {"messages": ["first message"]}

def replace_messages(state: State):
    # Bypass the reducer and replace the entire messages list
    return {"messages": Overwrite(["replacement message"])}
将你的值用Overwrite去包装起来，那么reducer就不会处理这个值了。而是直接覆盖

请求的时候可以用
{"messages": {"__overwrite__": ["replacement message"]}}

"""


class SuperState(TypedDict):
    """super智能体的状态维护 - 数据载体
    1 随单次工作流执行而生：从初始化到结束，状态持续更新，可持久化（checkpoint）
    2 高频修改
    3 属于「单次工作流请求」
    4 保存执行过程中的所有数据，在节点间传递信息
    """

    code: NotRequired[int | None]  # 判断状态 0 正常 1 异常
    err_message: NotRequired[str | None]  # 错误信息

    # messages: Annotated[list[AnyMessage], add_messages]  # 核心交互信息
    messages: NotRequired[Annotated[list[AnyMessage], add_messages]]  # 核心交互信息

    user_guidance: NotRequired[Dict | None]  # 用户反馈信息
    data: NotRequired[Dict | None]  # 核心结果信息存储
    human_in_loop_node: NotRequired[str | None]  # 人类反馈的节点
    todos: NotRequired[list | None]  # 任务列表todo-list
    sandbox_id: NotRequired[str | None]  # 沙盒id, local: 本地


class SuperContext(TypedDict):
    """Runtime 驱动工作流 / Agent 执行的「引擎」
    1 负责调度节点、更新状态、处理生命周期、提供运行环境
    2 逻辑 / 环境（动态）：是执行逻辑的引擎 + 运行环境（包含配置、上下文、工具实例等）
    2 调度节点执行、处理状态更新、管理生命周期（启动 / 暂停 / 终止）、提供依赖（如工具、模型实例）
    3 随服务 / 进程启动而生：Runtime 实例通常常驻，可处理多次工作流执行（复用工具 / 模型连接）
    4 属于「整个服务 / 框架」（比如 Agent 服务进程）
    """

    thread_id: str
    task_dir: NotRequired[str | None]
    model: NotRequired[str | None]
    models: NotRequired[Dict | None]
    config: NotRequired[Dict | None]
