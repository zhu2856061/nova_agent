# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
from typing import Any

import reflex as rx
from app.components.common.tab_components import TabMenu, tab_content, tab_trigger
from app.states.state import _DEFAULT_NAME, _PROMPT_DIR, _TASK_DIR

logger = logging.getLogger(__name__)


class PromptSettingsState(rx.State):
    tabs: list[TabMenu] = [
        TabMenu(
            value="extract_setting",
            label="抽取设定",
            icon="brain",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="core_seed",
            label="种子设定",
            icon="brain",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="character_dynamics",
            label="角色设定",
            icon="brain",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="world_building",
            label="世界观构建",
            icon="brain",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="plot_arch",
            label="情节架构",
            icon="brain",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="chapter_blueprint",
            label="章节目录",
            icon="list-tree",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="first_chapter_draft",
            label="首章提示词",
            icon="brain",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="create_character_state",
            label="首章前创建角色状态",
            icon="bike",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="next_chapter_draft",
            label="下一章提示词",
            icon="gpu",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="global_summary",
            label="下一章前生成全局摘要",
            icon="earth",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="update_character_state",
            label="下一章前更新角色状态",
            icon="layout-list",  # 图标（Reflex内置图标名）
            component="editor",
        ),
        TabMenu(
            value="summarize_recent_chapters",
            label="下一章前生成近3章期概要",
            icon="list-tree",  # 图标（Reflex内置图标名）
            component="editor",
        ),
    ]

    current_tab = "extract_setting"
    saving = False
    current_chat = _DEFAULT_NAME
    is_prompt_settings_modal_open = False

    _workspace = {current_chat: {}}
    for item in tabs:
        if item.value not in _workspace[current_chat]:
            _workspace[current_chat][item.value] = ""

    @rx.event
    def set_is_prompt_settings_modal_open(self, is_open: bool):
        self.is_prompt_settings_modal_open = is_open

    @rx.event
    def change_tab_value(self, val):
        self.current_tab = val

    @rx.event
    def set_prompt_content(self, value: str):
        self._workspace[self.current_chat][self.current_tab] = value

    @rx.var
    def get_prompt_content(self) -> str:
        if not self._workspace[self.current_chat][self.current_tab]:
            try:
                with open(
                    f"{_TASK_DIR}/{self.current_chat}/prompt/{self.current_tab}.md"
                ) as f:
                    return f.read()
            except Exception:
                with open(f"{_PROMPT_DIR}/ainovel/{self.current_tab}.md") as f:
                    return f.read()
        else:
            return self._workspace[self.current_chat][self.current_tab]

    # 保存输出内容
    @rx.event
    def save_prompt_content(self, form_data: dict[str, Any]):
        try:
            self.saving = True
            prompt = form_data["prompt"]
            if not prompt:
                yield rx.toast("内容为空")
                self.saving = False
                return
            """保存输出内容的逻辑"""
            # 示例：保存到本地存储（或提交到后端）
            os.makedirs(f"{_TASK_DIR}/{self.current_chat}/prompt", exist_ok=True)
            with open(
                f"{_TASK_DIR}/{self.current_chat}/prompt/{self.current_tab}.md", "w"
            ) as f:
                f.write(prompt)
            self._workspace[self.current_chat][self.current_tab] = prompt
            self.saving = False
            yield rx.toast("内容已成功保存")

        except Exception as e:
            self.saving = False
            yield rx.toast("保存失败")
            logger.error(e)


def baisc_comp() -> rx.Component:
    return rx.form(
        rx.vstack(
            rx.text_area(
                placeholder="在这里输入你的提示词...",
                value=PromptSettingsState.get_prompt_content,
                on_change=PromptSettingsState.set_prompt_content,
                width="100%",
                height="100%",
                border_radius="5px",
                border="1px solid",
                # padding="0.2em",
                font_size="1em",
                resize="vertical",
                id="prompt",
                style={
                    "overflow-y": "auto",  # 垂直溢出时显示滚动条
                    "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                },
            ),
            rx.button(
                "保存",
                loading=PromptSettingsState.saving,
                disabled=PromptSettingsState.saving,
                type="submit",  # 显式设置为普通按钮
            ),
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        on_submit=PromptSettingsState.save_prompt_content,
    )


def chapter_draft_tab_main() -> rx.Component:
    """小说工作区（优化后的垂直标签页组件）"""
    # 1. 定义标签列表（可动态从state读取，此处示例静态配置）
    return rx.tabs.root(
        # 标签列表（垂直布局）
        rx.tabs.list(
            rx.foreach(PromptSettingsState.tabs, tab_trigger),
            width="22em",
            height="100%",
            background_color=rx.color("mauve", 2),  # 标签列表背景色
            border_radius="5px",
            padding="0.5em",
            gap="1.5em",
            flex_direction="column",  # 垂直排列
        ),
        # 标签内容区
        rx.foreach(PromptSettingsState.tabs, lambda _: tab_content(_, baisc_comp())),
        on_change=PromptSettingsState.change_tab_value,
        # 标签页核心配置
        default_value=PromptSettingsState.current_tab,  # 默认选中第一个标签
        orientation="vertical",  # 垂直布局
        width="100%",
        height="100%",
        display="flex",
        gap="0.5em",
    )


def prompt_settings_modal(trigger) -> rx.Component:
    """用于创建新聊天的模态框组件"""
    return rx.dialog.root(  # 对话框根组件
        rx.dialog.trigger(trigger),  # 对话框触发器，传入的参数作为触发元素
        rx.dialog.content(  # 对话框内容区域
            rx.dialog.title(
                rx.hstack(
                    rx.text(
                        "Prompt Settings",
                        size="4",
                        weight="bold",
                    ),
                    margin_bottom="1em",
                    gap="0.5em",
                ),
            ),
            chapter_draft_tab_main(),
            background_color=rx.color("mauve", 1),  # 使用mauve色系的第1种颜色作为背景
            border_radius="0.5em",  # 圆角边框
            box_shadow="lg",  # 增加阴影提升层次感
            max_width="1000px",  # 限制最大宽度，提升可读性
            height="500px",
            padding="1.5em",  # 适当增加内边距
            transition="all 0.2s ease-in-out",
        ),
        open=PromptSettingsState.is_prompt_settings_modal_open,  # 控制模态框是否打开的状态
        on_open_change=PromptSettingsState.set_is_prompt_settings_modal_open,  # 模态框打开状态变化时调用的方法
    )
