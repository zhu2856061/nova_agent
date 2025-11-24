# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Union

import reflex as rx


def headbar(badge: Union[rx.Var[str], str]) -> rx.Component:
    """导航栏组件，显示当前聊天、创建新聊天按钮和侧边栏按钮"""
    return rx.hstack(  # 水平堆叠布局
        # 侧边栏收起/展开切换按钮
        rx.hstack(
            # 显示当前聊天的徽章
            rx.badge(
                badge,  # 显示当前聊天标题
                # 信息提示框，鼠标悬停时显示提示信息
                rx.tooltip(
                    rx.icon("info", size=14),  # 信息图标
                    content="The current selected chat",  # 提示内容
                ),
                size="3",  # 徽章大小
                variant="soft",  # 柔和样式的徽章变体
                margin_inline_end="auto",  # 右侧外边距自动，将后续元素推到右边
            ),
            spacing="2",
        ),
        align_items="right",  # 子元素垂直居中
        padding="12px",  # 内边距12px
        border_bottom=f"1px solid {rx.color('mauve', 3)}",  # 底部边框，使用mauve色系的第3种颜色
        background_color=rx.color("mauve", 2),  # 使用mauve色系的第2种颜色作为背景
    )
