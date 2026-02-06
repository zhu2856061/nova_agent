# -*- coding: utf-8 -*-
# @Time   : 2025/11/14 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from dataclasses import dataclass
from typing import Optional

import reflex as rx


@dataclass(kw_only=True)
class TabMenu:
    value: str  # 标签唯一标识（用于切换）
    label: str  # 标签显示文本
    component: str
    disabled: bool = False  # 是否禁用标签
    icon: Optional[str] = None  # 标签图标（可选）


# 3. 生成标签触发按钮（统一样式）--------------------------
def tab_trigger(tab: TabMenu) -> rx.Component:
    """生成标签触发按钮（含图标、文字、状态样式）"""
    return rx.tabs.trigger(
        # 图标（可选）
        rx.cond(
            tab.icon is not None,
            rx.icon(tab.icon, size=16, margin_right="0.6em"),
            rx.box(),  # 无图标时占位，避免布局抖动
        ),
        tab.label,
        value=tab.value,
        height="3.2em",
        font_size="1.0em",
        _hover={
            "background_color": rx.color("mauve", 5),
            "transition": "background-color 0.2s ease",
        },
        width="100%",
        display="flex",
        align_items="center",
        justify_content="flex-start",
        border_radius="5px",
    )


# 4. 生成标签内容（延迟渲染）--------------------------
def tab_content(tab: TabMenu, component) -> rx.Component:
    """生成标签内容区（支持自定义组件）"""
    return rx.tabs.content(
        # 内容容器（添加样式优化）
        rx.box(
            component,
            width="100%",
            height="100%",
            # min_height="30em",  # 最小高度（避免内容过短时布局塌陷）
            border_radius="5px",
            box_shadow="0 2px 10px rgba(0,0,0,0.05)",  # 轻微阴影（提升层次感）
            # padding="1.5em",  # 内容区内边距
            overflow="auto",  # 内容超出时滚动
        ),
        value=tab.value,
        width="100%",
        height="100%",
    )
