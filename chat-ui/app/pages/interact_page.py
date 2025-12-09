# # -*- coding: utf-8 -*-
# # @Time   : 2025/09/24 10:24
# # @Author : zip
# # @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, cast

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
from app.globel_var import (
    _SELECTED_MODELS,
    AINOVEL_TABMENU,
    DEFAULT_CHAT,
    INSTERACT_TASK_DIR,
    MENUS,
    PROMPT_DIR,
)

logger = logging.getLogger(__name__)


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
        _task_dir = INSTERACT_TASK_DIR
        _prompt_dir = PROMPT_DIR

        _is_human_in_loop = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # 初始状态
            self.menus = MENUS
            self.params_fields: list[Parameters] = [
                Parameters(
                    mkey="model",
                    mtype="select",
                    mvalue="basic",
                    mvaluetype="str",
                    mselected=_SELECTED_MODELS,
                ),
            ]

            # 初始化参数
            self.tabs: list[TabMenu] = AINOVEL_TABMENU

            self._init_workspace(self.current_chat)

        def _init_workspace(self, val: str):
            self._workspace[val] = {}
            for tab in self.tabs:
                self._workspace[val][tab.value] = {
                    "input_content": "",
                    "output_content": "",
                    "final_content": "",
                }
            self.current_chat = val
            self._show_workspace_all_content()

        # 获得badge
        @rx.var
        async def get_badge(self) -> str:
            """获得badge"""
            return self.title + " - " + self.current_chat

        # 创建会话窗口的提交事件
        @rx.event
        async def create_workspace(self, form_data: dict[str, Any]):
            new_chat_name = form_data["new_chat_name"]
            self._init_workspace(new_chat_name)
            shared = await self.get_state(PromptSettingsState)
            shared._init_workspace(new_chat_name)

        # 获得所有会话窗口名称
        @rx.var
        async def get_workspace_names(self) -> list[str]:
            return list(self._workspace.keys())

        # 设置当前会话窗口名称
        @rx.event
        async def set_workspace_name(self, name: str):
            self.current_chat = name
            # 获取 State1 实例，修改其变量
            shared = await self.get_state(PromptSettingsState)
            await shared.set_workspace_name(name)

        # 删除会话窗口
        @rx.event
        async def del_workspace(self, name: str):
            try:
                """Delete the current chat."""
                if name not in self._workspace:
                    return
                del self._workspace[name]
                if os.path.exists(f"{self._task_dir}/{self.current_chat}"):
                    shutil.rmtree(f"{self._task_dir}/{self.current_chat}")

                if len(self._workspace) == 0:
                    self._init_workspace(DEFAULT_CHAT)
                    self.current_chat = DEFAULT_CHAT

                if self.current_chat not in self._workspace:
                    self.current_chat = list(self._workspace.keys())[0]

                shared = await self.get_state(PromptSettingsState)
                await shared.del_prompt_content(name, self.current_chat)

            except Exception as e:
                yield rx.toast("删除失败")
                logger.error(e)

        # 获得当前会话内容 input_content
        @rx.var
        async def get_workspace_input_content(self) -> str:
            return self._workspace[self.current_chat][self.current_tab]["input_content"]

        @rx.event
        async def set_workspace_input_content(self, val):
            self._workspace[self.current_chat][self.current_tab]["input_content"] = val

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

        def _show_workspace_all_content(self):
            try:
                for item in self.tabs:
                    if os.path.exists(
                        f"{self._task_dir}/{self.current_chat}/history/{item.value}.md"
                    ):
                        with open(
                            f"{self._task_dir}/{self.current_chat}/history/{item.value}.md",
                            "r",
                        ) as f:
                            self._workspace[self.current_chat][item.value] = json.loads(
                                f.read()
                            )

            except Exception as e:
                logger.error(e)

        @rx.event
        async def save_workspace_all_content(self):
            try:
                self.is_saving = True
                os.makedirs(
                    f"{self._task_dir}/{self.current_chat}/history", exist_ok=True
                )
                with open(
                    f"{self._task_dir}/{self.current_chat}/history/{self.current_tab}.md",
                    "w",
                ) as f:
                    tmp = self._workspace[self.current_chat][self.current_tab]
                    f.write(json.dumps(tmp, ensure_ascii=False))
                self.is_saving = False
                yield rx.toast("内容已成功保存")
            except Exception as e:
                self.is_saving = False
                logger.error(e)
                yield rx.toast(f"保存失败: {e}")

        # 对话框的提交事件
        @rx.event
        async def submit_input_bar_question(self, form_data: dict[str, Any]):
            try:
                question = form_data["question"]

                context = {
                    "thread_id": self.current_chat,
                    "config": {
                        "prompt_dir": f"{INSTERACT_TASK_DIR}/{self.current_chat}/prompt",
                        "result_dir": f"{INSTERACT_TASK_DIR}/{self.current_chat}",
                    },
                }
                for item in self.params_fields:
                    if item.mvaluetype == "dict":
                        context[item.mkey] = json.loads(item.mvalue)
                    elif item.mvaluetype == "int":
                        context[item.mkey] = int(item.mvalue)
                    elif item.mvaluetype == "float":
                        context[item.mkey] = float(item.mvalue)
                    else:
                        context[item.mkey] = item.mvalue

                is_start_answer = True
                is_start_thinking = True
                uid4 = str(uuid.uuid4())

                self.is_processing = True
                _current_chapter_id = 1
                if os.path.exists(f"{INSTERACT_TASK_DIR}/{self.current_chat}/chapter"):
                    # 确定当前属于第几章
                    dir_path = Path(f"{INSTERACT_TASK_DIR}/{self.current_chat}/chapter")
                    file_count = sum(
                        1
                        for item in dir_path.iterdir()
                        if item.is_dir() and item.name.startswith("chapter")
                    )
                    if file_count == 0:
                        _current_chapter_id = 1
                    else:
                        if os.path.exists(
                            f"{INSTERACT_TASK_DIR}/{self.current_chat}/chapter/chapter_{file_count}/chapter_draft.md"
                        ):
                            _current_chapter_id = file_count + 1
                        else:
                            _current_chapter_id = file_count

                self._workspace[self.current_chat][self.current_tab][
                    "output_content"
                ] = ""

                # 初始化
                state = {
                    "messages": {
                        "type": "override",
                        "value": [
                            {
                                "role": "user",
                                "content": question,
                            },
                        ],
                    },
                    "user_guidance": {
                        "human_in_loop_value": question,
                        "current_chapter_id": _current_chapter_id,
                    },
                }

                async for value in get_nova_agent_api(
                    url_name=f"ainovel_{self.current_tab}",
                    trace_id=uid4,
                    state=state,
                    context=context,
                ):
                    # 获取最终结果
                    if value and value.get("is_final"):
                        for _, item in cast(dict, value["final_content"]).items():
                            self._workspace[self.current_chat][self.current_tab][
                                "final_content"
                            ] = str(item)

                    if value and value.get("type", None) is not None:
                        if value["type"] == "system":
                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += value["content"]

                        if value["type"] == "thought":
                            if is_start_thinking:
                                self._workspace[self.current_chat][self.current_tab][
                                    "output_content"
                                ] += "\n\n🤔 Thinking...\n\n"
                                is_start_thinking = False

                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += value["content"]

                        if value["type"] == "answer":
                            if is_start_answer:
                                self._workspace[self.current_chat][self.current_tab][
                                    "output_content"
                                ] += "\n\n✨ Answering...\n\n"
                                is_start_answer = False

                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += value["content"]
                        if value["type"] == "error":
                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += f"<span style='color:red'>{value['content']}</span>"
                        yield

                self.is_processing = False
            except Exception as e:
                logger.error(e)
                self.is_processing = False
                yield rx.toast("处理失败")

    def _editor_page_main() -> rx.Component:
        return rx.vstack(
            editor_prompt_bar(
                State.current_tab,
                State.is_saving,
                State.get_workspace_final_content,
                State.save_workspace_all_content,
            ),
            editor_input_bar(
                State.get_workspace_input_content,
                State.set_workspace_input_content,
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
