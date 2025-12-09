# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os

import reflex as rx
from app.components.common.tab_components import TabMenu, tab_content, tab_trigger
from app.globel_var import (
    AINOVEL_PROMPT_TABMENU,
    DEFAULT_CHAT,
    INSTERACT_TASK_DIR,
    PROMPT_DIR,
)

logger = logging.getLogger(__name__)


class PromptSettingsState(rx.State):
    tabs: list[TabMenu] = []
    saving = False
    current_chat = DEFAULT_CHAT

    current_tab = "extract_setting"
    is_prompt_settings_modal_open = False
    _workspace = {}
    _task_dir = INSTERACT_TASK_DIR
    _prompt_dir = PROMPT_DIR

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tabs: list[TabMenu] = AINOVEL_PROMPT_TABMENU

        self._init_workspace(self.current_chat)

    def _init_workspace(self, val: str):
        self.current_chat = val
        _raw_prompt_conyent = {}
        for item in self.tabs:
            if os.path.exists(
                f"{self._task_dir}/{self.current_chat}/prompt/{item.value}.md"
            ):
                with open(
                    f"{self._task_dir}/{self.current_chat}/prompt/{item.value}.md"
                ) as f:
                    _raw_prompt_conyent[item.value] = f.read()
            else:
                with open(f"{self._prompt_dir}/ainovel/{item.value}.md") as f:
                    _raw_prompt_conyent[item.value] = f.read()

        self._workspace[self.current_chat] = _raw_prompt_conyent

        os.makedirs(f"{self._task_dir}/{self.current_chat}/prompt", exist_ok=True)

        # 保存到本地存储（或提交到后端）
        for item in self.tabs:
            with open(
                f"{self._task_dir}/{self.current_chat}/prompt/{item.value}.md", "w"
            ) as f:
                tmp = self._workspace[self.current_chat][item.value]
                f.write(tmp)

    @rx.event
    async def set_is_prompt_settings_modal_open(self, is_open: bool):
        self.is_prompt_settings_modal_open = is_open

    @rx.event
    async def set_tab_value(self, val):
        self.current_tab = val

    @rx.event
    async def set_workspace_name(self, name: str):
        self.current_chat = name

    # 修改内容
    @rx.event
    async def update_prompt_content(self, value: str):
        self._workspace[self.current_chat][self.current_tab] = value

    # 获取内容
    @rx.var
    async def get_prompt_content(self) -> str:
        return self._workspace[self.current_chat][self.current_tab]

    # 保存prompt内容
    @rx.event
    async def save_prompt_content(self):
        try:
            os.makedirs(f"{self._task_dir}/{self.current_chat}/prompt", exist_ok=True)
            self.saving = True
            """保存输出内容的逻辑"""
            # 示例：保存到本地存储（或提交到后端）
            for item in self.tabs:
                with open(
                    f"{self._task_dir}/{self.current_chat}/prompt/{item.value}.md", "w"
                ) as f:
                    tmp = self._workspace[self.current_chat][item.value]
                    f.write(tmp)

            self.saving = False
            yield rx.toast("内容已成功保存")

        except Exception as e:
            self.saving = False
            logger.error(e)
            yield rx.toast(f"保存失败: {e}")

    # 删除prompt内容
    @rx.event
    async def del_prompt_content(self, name: str, val: str):
        try:
            self.saving = True
            if name not in self._workspace:
                return
            del self._workspace[name]

            if len(self._workspace) == 0:
                self._init_workspace(DEFAULT_CHAT)
                self.current_chat = DEFAULT_CHAT

            self.current_chat = val

            if self.current_chat not in self._workspace:
                self.current_chat = list(self._workspace.keys())[0]

            self.saving = False

        except Exception as e:
            self.saving = False
            logger.error(e)


def baisc_comp() -> rx.Component:
    return rx.form(
        rx.vstack(
            rx.text_area(
                value=PromptSettingsState.get_prompt_content,
                on_change=PromptSettingsState.update_prompt_content,
                width="100%",
                height="100%",
                min_height="0",
                border_radius="8px",
                border=f"1px solid {rx.color('mauve', 6)}",
                font_size="0.94rem",
                resize="vertical",
                # padding="0.75rem",
                background_color=rx.color("mauve", 1),
                _focus={"border_color": rx.color("mauve", 8)},
                # === 美化滚动条（现代浏览器）===
                style={
                    # Firefox
                    "scrollbar-width": "thin",
                    "scrollbar-color": f"{rx.color('mauve', 7)} transparent",
                    # WebKit (Chrome, Safari, Edge)
                    "&::-webkit-scrollbar": {
                        "width": "6px",
                    },
                    "&::-webkit-scrollbar-track": {
                        "background": "transparent",
                        "border-radius": "3px",
                    },
                    "&::-webkit-scrollbar-thumb": {
                        "background": rx.color("mauve", 7),
                        "border-radius": "3px",
                    },
                    "&::-webkit-scrollbar-thumb:hover": {
                        "background": rx.color("mauve", 9),
                    },
                },
                id="prompt",
            ),
            width="100%",
            height="100%",
            spacing="0",
        ),
        width="100%",
        height="100%",
    )


def prompt_tabs() -> rx.Component:
    """小说工作区（优化后的垂直标签页组件）"""
    # 1. 定义标签列表（可动态从state读取，此处示例静态配置）
    return rx.tabs.root(
        # 标签列表（垂直布局）
        rx.tabs.list(
            rx.foreach(PromptSettingsState.tabs, tab_trigger),
            width="230px",
            height="100%",
            background_color=rx.color("mauve", 2),
            border_radius="10px",
            # padding="0.75rem",
            gap="0.5rem",
            flex_direction="column",
            flex_shrink="0",
            overflow_y="auto",  # 关键：开启垂直滚动
            overflow_x="hidden",  # 禁止横向滚动
            # === 美化滚动条（现代浏览器）===
            style={
                # Firefox
                "scrollbar-width": "thin",
                "scrollbar-color": f"{rx.color('mauve', 7)} transparent",
                # WebKit (Chrome, Safari, Edge)
                "&::-webkit-scrollbar": {
                    "width": "6px",
                },
                "&::-webkit-scrollbar-track": {
                    "background": "transparent",
                    "border-radius": "3px",
                },
                "&::-webkit-scrollbar-thumb": {
                    "background": rx.color("mauve", 7),
                    "border-radius": "3px",
                },
                "&::-webkit-scrollbar-thumb:hover": {
                    "background": rx.color("mauve", 9),
                },
            },
        ),
        # === 右侧内容区 ===
        rx.box(
            rx.foreach(
                PromptSettingsState.tabs,
                lambda tab: tab_content(tab, baisc_comp()),
            ),
            width="100%",
            height="100%",
            # padding="0.75rem",  # 内容区内边距
            background_color=rx.color("mauve", 1),
            border_radius="10px",
            overflow="hidden",
        ),
        on_change=PromptSettingsState.set_tab_value,
        # 标签页核心配置
        default_value=PromptSettingsState.current_tab,  # 默认选中第一个标签
        orientation="horizontal",  # 垂直布局
        width="100%",
        height="100%",
        display="flex",
        gap="1rem",  # 标签列与内容区间距
        align_items="stretch",
    )


def prompt_settings_modal(trigger) -> rx.Component:
    """用于创建新聊天的模态框组件"""
    return rx.dialog.root(  # 对话框根组件
        rx.dialog.trigger(trigger),  # 对话框触发器，传入的参数作为触发元素
        rx.dialog.content(
            # === 标题栏：标题 + 保存按钮 + 关闭按钮 ===
            rx.box(
                rx.dialog.title(
                    rx.hstack(
                        rx.text("Prompt Settings", size="2", weight="bold"),
                        rx.hstack(
                            rx.icon_button(
                                rx.icon("save", size=18),
                                on_click=PromptSettingsState.save_prompt_content,
                                size="1",
                                border_radius="lg",
                                padding="0.35rem",
                                background_color=rx.color("mauve", 5),
                                color=rx.color("mauve", 11),
                                variant="soft",
                                cursor="pointer",
                                _hover={
                                    "background_color": rx.color("mauve", 7),
                                    "transform": "scale(1.05)",
                                },
                            ),
                            # === 关闭按钮（顶部右上角）===
                            rx.dialog.close(
                                rx.icon_button(
                                    rx.icon("x", size=18),
                                    size="1",
                                    padding="0.35rem",
                                    border_radius="lg",
                                    background_color=rx.color("mauve", 5),
                                    color=rx.color("mauve", 11),
                                    variant="soft",
                                    cursor="pointer",
                                    _hover={
                                        "background_color": rx.color("mauve", 8),
                                        "color": rx.color("mauve", 12),
                                        "transform": "scale(1.05)",
                                    },
                                ),
                            ),
                            spacing="2",
                        ),
                        justify_content="space-between",
                        align="center",
                        width="100%",
                    ),
                    margin_bottom="0.3rem",  # 避免标题与内容间距过大
                ),
                position="relative",  # 让关闭按钮绝对定位
            ),
            # === 内容区：自适应高度 + 滚动 ===
            rx.box(
                prompt_tabs(),
                flex="1",  # 关键：占满剩余高度
                min_height="0",  # 允许 flex 压缩
                overflow="hidden",  # 内容区不外 100% 滚动
            ),
            # === 关键：强制固定宽高 ===
            width="800px",  # 必须写在 content 上
            height="500px",  # 必须写在 content 上
            max_width="800px",  # 禁止超过
            max_height="500px",  # 禁止超过
            min_width="800px",  # 禁止缩小（可选）
            min_height="500px",  # 禁止缩小（可选）
            # === 模态框样式 ===
            background_color=rx.color("mauve", 1),
            border_radius="0.75rem",
            box_shadow="xl",
            padding="0.8rem",  # 外边距适中
            display="flex",
            flex_direction="column",
            gap="0.75rem",
            transition="all 0.2s ease-in-out",
        ),
        # width="1000px",
        # height="300px",  # 略增高度，容纳间距
        open=PromptSettingsState.is_prompt_settings_modal_open,  # 控制模态框是否打开的状态
        on_open_change=PromptSettingsState.set_is_prompt_settings_modal_open,  # 模态框打开状态变化时调用的方法
    )
