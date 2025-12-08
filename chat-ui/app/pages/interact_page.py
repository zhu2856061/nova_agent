# # -*- coding: utf-8 -*-
# # @Time   : 2025/09/24 10:24
# # @Author : zip
# # @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import json
from re import S
from typing import Any

import reflex as rx

from app.api.nova_agent_api import get_nova_agent_api
from app.components.common.baisc_components import basic_page
from app.components.common.sidebar_components import SideMenu
from app.components.common.tab_components import TabMenu, tab_trigger
from app.components.interact.edit_bar import (
    Parameters,
    editor_input_bar,
    editor_prompt_bar,
    editor_show_bar,
)
from app.components.interact.prompt_settings import PromptSettingsState
from app.globel_var import AINOVEL_TABMENU, DEFAULT_CHAT, MENUS, PARAMS_FIELDS


def _create_interact_page(title_name: str) -> rx.Component:
    """
    工厂函数：为每个不同的 Agent 创建完全独立的页面 + 状态
    """

    class State(rx.State):
        """聊天页面状态"""

        brand = "NovaAI"
        logo = "../novaai.png"

        title = title_name

        current_chat = DEFAULT_CHAT

        is_processing = False
        is_saving = False
        menus: list[SideMenu] = MENUS
        params_fields: list[Parameters] = []

        tabs: list[TabMenu] = []
        current_tab = "extract_setting"
        _workspace = {}

        _is_human_in_loop = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # 初始状态
            self.menus = MENUS
            self.params_fields: list[Parameters] = PARAMS_FIELDS

            # 初始化参数
            self.tabs: list[TabMenu] = AINOVEL_TABMENU

            self._init_workspace_content(self.current_chat)

        # async def on_load(self):  # 新增页面加载时执行的异步初始化
        #     shared1 = await self.get_state(HeaderBarState)
        #     shared1.init_header_bar_state(self)

        #     shared2 = await self.get_state(EditState)
        #     shared2.init_edit_state(self)

        def _init_workspace_content(self, val: str):
            self._workspace[val] = {}
            for tab in self.tabs:
                self._workspace[val][tab.value] = {
                    "input_content": "",
                    "output_content": "",
                    "final_content": "",
                }

        # 获得badge
        @rx.var
        async def get_badge(self) -> str:
            """获得badge"""
            return self.title + " - " + self.current_chat

        # 创建会话窗口的提交事件
        @rx.event
        async def create_workspace(self, form_data: dict[str, Any]):
            new_chat_name = form_data["new_chat_name"]
            self._init_workspace_content(new_chat_name)
            await self.set_workspace_name(new_chat_name)

        # 获得所有会话窗口名称
        @rx.var
        async def get_workspace_names(self) -> list[str]:
            return list(self._workspace.keys())

        # @rx.var
        # async def get_workspace(self) -> list[str]:
        #     return self._workspace[self.current_chat]

        # 设置当前会话窗口名称
        @rx.event
        async def set_workspace_name(self, name: str):
            self.current_chat = name
            # 获取 State1 实例，修改其变量
            shared = await self.get_state(PromptSettingsState)
            shared._init_prompt_content_and_current_chat(name)

        # 删除会话窗口
        @rx.event
        async def del_workspace(self, name: str):
            """Delete the current chat."""
            if name not in self._workspace:
                return
            del self._workspace[name]

            if len(self._workspace) == 0:
                self._init_workspace_content(self.default_chat_name)
                self.current_chat = self.default_chat_name

            if self.current_chat not in self._workspace:
                self.current_chat = list(self._workspace.keys())[0]

        # 获得当前会话内容 input_content
        @rx.var
        async def get_workspace_input_content(self) -> str:
            return self._workspace[self.current_chat][self.current_tab]["input_content"]

        # 获得当前会话内容 output_content
        @rx.var
        async def get_workspace_output_content(self) -> str:
            return self._workspace[self.current_chat][self.current_tab][
                "output_content"
            ]

        # 获得当前会话内容 final_content
        @rx.var
        async def get_workspace_final_content(self) -> str:
            return self._workspace[self.current_chat][self.current_tab]["final_content"]

        @rx.event
        async def set_workspace_final_content(self, val):
            self._workspace[self.current_chat][self.current_tab]["final_content"] = val

        @rx.event
        async def set_tab_value(self, val):
            self.current_tab = val

        # 修改设置的提交事件
        @rx.event
        async def submit_input_bar_settings(self, form_data: dict[str, Any]):
            try:
                for k, v in form_data.items():
                    for item in self.params_fields:
                        if item.mkey == k:
                            if item.mvaluetype == "float":
                                item.mvalue = float(v)
                            elif item.mvaluetype == "int":
                                item.mvalue = int(v)
                            elif item.mvaluetype == "dict":
                                item.mvalue = json.dumps((json.loads(v)))
                            else:
                                item.mvalue = v
            except Exception as e:
                return rx.window_alert(str(e))

        @rx.event
        async def show_workspace_all_content(self):
            pass

        @rx.event
        async def save_workspace_all_content(self):
            pass

        # 对话框的提交事件
        @rx.event
        async def submit_input_bar_question(self, form_data: dict[str, Any]):
            self.is_processing = True

            self.is_processing = False

    def _editor_page_main() -> rx.Component:
        return rx.vstack(
            editor_prompt_bar(
                State.current_tab,
                State.is_saving,
                State.get_workspace_final_content,
                State.save_workspace_all_content,
            ),
            editor_input_bar(
                State.submit_input_bar_question,
                State.params_fields,
                State.submit_input_bar_settings,
                State.is_processing,
            ),
            editor_show_bar(
                State.get_workspace_output_content,
                State.get_workspace_final_content,
                State.set_workspace_final_content,
            ),
            width="100%",
            height="100%",
            # 核心：缩小组件间垂直间距
            spacing="2",  # 替代默认间距，可根据需求调整（如0.3em/0.4em）
            # 保留垂直居中（可选，根据页面需求）
            align_items="stretch",  # 子组件占满宽度，保持布局统一
            justify_content="flex-start",  # 顶部对齐，避免间距分散
            # 移除不必要的外边距（防止子组件自带间距叠加）
            margin="0",
            # padding="0 0.2em",  # 仅保留左右内边距，上下无padding
        )

    def _page_main():
        return rx.tabs.root(
            # 标签列表（垂直布局）
            rx.tabs.list(
                rx.foreach(State.tabs, tab_trigger),
                width="12em",
                height="100%",
                background_color=rx.color("mauve", 2),  # 标签列表背景色
                border_radius="5px",
                padding="0.2em",
                gap="1.5em",
                flex_direction="column",  # 垂直排列
            ),
            # 标签内容区
            _editor_page_main(),
            # rx.foreach(State.tabs, lambda _: editor_component_form(_, State)),
            on_change=State.set_tab_value,
            # 标签页核心配置
            default_value=State.current_tab,  # 默认选中第一个标签
            orientation="vertical",  # 垂直布局
            width="100%",
            height="100%",
            display="flex",
            gap="0.5em",
            # padding_bottom="5px",
            # padding_top="5px",
            padding="0.5em 0.5em",  # 仅保留左右内边距，上下无padding
        )

    def _page() -> rx.Component:
        return basic_page(
            State.brand,
            State.title,
            State.create_workspace,
            State.get_workspace_names,
            State.set_workspace_name,
            State.del_workspace,
            State.logo,
            State.menus,
            State.get_badge,
            _page_main(),
        )

    return _page()


# ==================== 使用方式（完全独立实例）===================


interact_page = _create_interact_page("Interact")
