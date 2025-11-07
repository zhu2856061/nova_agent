# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

import reflex as rx

logger = logging.getLogger(__name__)

_DEFAULT_NAME = "Nova"
_INTRODUCTION = "Hi! I'm **Nova**, a helpful assistant."
_SELECTED_MODELS = ["basic", "reasoning", "basic_no_thinking", "deepseek", "gemini"]
_TASK_DIR = "../merlin"


@dataclass(kw_only=True)
class Message:
    role: str = field(default="assistant")
    content: str = field(default="")


@dataclass(kw_only=True)
class FunctionMenu:
    title: str
    icon: str
    tobe: str = "/"
    children: Optional[List["FunctionMenu"]] = None


class Parameters(rx.Model):
    mkey: str
    mtype: str
    mvalue: Any
    mvaluetype: str
    mselected: Optional[List[Any]]


class State(rx.State):
    # Whether we are processing the question.
    processing: bool = False

    # Whether the new chat modal is open.
    is_new_chat_modal_open: bool = False
    is_params_settings_modal_open: bool = False
    sidebar_visible: bool = True  # 侧边栏是否展开
    function_menu: List[FunctionMenu] = [
        FunctionMenu(
            title="Chat",
            icon="message-circle-more",
            children=[
                FunctionMenu(
                    title="llm",
                    icon="message-circle-more",
                    tobe="/chat/llm",
                ),
            ],
        ),
        FunctionMenu(
            title="Agent",
            icon="bot-message-square",
            children=[
                FunctionMenu(
                    title="memorizer",
                    icon="bot-message-square",
                    tobe="/agent/memorizer",
                ),
                FunctionMenu(
                    title="web_searcher",
                    icon="bot-message-square",
                    tobe="/agent/researcher",
                ),
                FunctionMenu(
                    title="wechat_searcher",
                    icon="bot-message-square",
                    tobe="/agent/wechat_researcher",
                ),
                FunctionMenu(
                    title="ainovel_architect",
                    icon="bot-message-square",
                    tobe="/agent/ainovel_architect",
                ),
                FunctionMenu(
                    title="ainovel_chapter",
                    icon="bot-message-square",
                    tobe="/agent/ainovel_chapter",
                ),
            ],
        ),
        FunctionMenu(
            title="Task",
            icon="clipboard-list",
            children=[
                FunctionMenu(
                    title="deepresearcher",
                    icon="clipboard-list",
                    tobe="/task/deepresearcher",
                ),
                FunctionMenu(
                    title="ainovel",
                    icon="clipboard-list",
                    tobe="/task/ainovel",
                ),
            ],
        ),
        FunctionMenu(
            title="Interact",
            icon="layout-dashboard",
            children=[
                FunctionMenu(
                    title="ainovel",
                    icon="layout-dashboard",
                    tobe="/interact/ainovel",
                ),
            ],
        ),
    ]

    @rx.event
    def set_is_new_chat_modal_open(self, is_open: bool):
        self.is_new_chat_modal_open = is_open

    @rx.event
    def set_is_params_settings_modal_open(self, is_open: bool):
        self.is_params_settings_modal_open = is_open

    # @rx.var
    # def get_function_menu(self) -> List[FunctionMenu]:
    #     return [item for item in self.function_menu]

    @rx.event
    def toggle_sidebar(self):
        """切换侧边栏展开/收起状态"""
        self.sidebar_visible = not self.sidebar_visible
