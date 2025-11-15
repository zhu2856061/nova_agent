# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx
from app.components.common.tab_components import tab_content, tab_trigger
from app.components.novel.core_interact_section import (
    editor_component_form,
)


def tab_content_selected(tab, state) -> rx.Component:
    return rx.cond(
        tab.component == "editor",
        tab_content(tab, editor_component_form(tab, state)),
        tab_content(tab, rx.box()),
    )


def novel_workspace(state) -> rx.Component:
    """小说工作区（优化后的垂直标签页组件）"""
    return rx.tabs.root(
        # 标签列表（垂直布局）
        rx.tabs.list(
            rx.foreach(state.novel_tabs, tab_trigger),
            width="12em",
            height="100%",
            background_color=rx.color("mauve", 2),  # 标签列表背景色
            border_radius="5px",
            padding="0.5em",
            gap="1.5em",
            flex_direction="column",  # 垂直排列
        ),
        # 标签内容区
        rx.foreach(state.novel_tabs, lambda _: tab_content_selected(_, state)),
        on_change=state.change_tab_value,
        # 标签页核心配置
        default_value=state.current_tab,  # 默认选中第一个标签
        orientation="vertical",  # 垂直布局
        width="100%",
        height="100%",
        display="flex",
        gap="0.5em",
    )
