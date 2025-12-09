# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import reflex as rx
from app.components.common.workspace_manager import (
    create_workspace_modal,
    workspace_drawer,
)


def headbar(
    badge, title, create_workspace, workspace_names, set_workspace, del_workspace
) -> rx.Component:
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
                    content="当前选中的聊天",  # 提示内容
                ),
                size="2",  # 徽章大小
                variant="soft",  # 柔和样式的徽章变体
                align="center",
            ),
            spacing="2",
            align_items="center",  # 垂直居中（保留）
        ),
        # === 右侧：创建聊天 + 侧边栏抽屉 ===
        rx.hstack(
            # 创建新聊天的模态框，使用消息加号图标作为触发器
            create_workspace_modal(
                rx.icon_button(
                    rx.icon("message-square-plus", size=18),
                    size="1",
                    border_radius="lg",  # 关键：圆角
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
                title,
                create_workspace.stop_propagation(),
            ),
            # 侧边栏组件，使用消息图标作为触发器
            workspace_drawer(
                rx.icon_button(
                    rx.icon("messages-square", size=18),
                    size="1",
                    border_radius="lg",  # 关键：圆角
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
                title,
                workspace_names,
                set_workspace,
                del_workspace,
            ),
            # 核心：靠右对齐 + 移除居中margin
            justify_content="flex-end",  # 子元素整体靠右
            align_items="center",  # 垂直居中（保留）
            width="100%",  # 占满父容器宽度（必须，否则靠右无效）
        ),
        # === 容器样式 ===
        padding_x="1rem",  # 左右内边距 16px
        padding_y="0.5rem",  # 上下内边距 12px
        background_color=rx.color("mauve", 3),
        top="0",
    )
