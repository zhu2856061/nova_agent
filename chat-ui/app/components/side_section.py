# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx


def sidebar_item(title: str, icon: str, url: str) -> rx.Component:
    """侧边栏单个菜单项组件"""
    return rx.box(
        rx.link(
            rx.hstack(
                rx.icon(tag=icon, margin_right="0.5em"),
                rx.text(title),
            ),
            href=url,
        ),
        padding="0.75em",
        background_color=rx.color("mauve", 2),
        border_radius="0.25em",
    )


def sidebar() -> rx.Component:
    """侧边栏整体组件"""
    return rx.box(
        rx.hstack(
            rx.avatar(name="NovaAI", src="novaai.png"),  # 替换为实际头像地址
            rx.text("NovaAI", size="6", weight="bold"),
            justify_content="center",
            align_items="center",
            # padding="0.1em",
            margin_bottom="0.5em",
        ),
        rx.divider(),
        rx.vstack(
            rx.text(
                "功能",
                size="4",
                weight="bold",
                padding_left="0.75em",
                align_items="center",
                justify_content="center",
                margin_top="0.5em",
            ),
            sidebar_item(title="Chat", icon="plus_square", url="/chat"),
            sidebar_item(title="Agent", icon="pencil", url="/agent"),
            sidebar_item(title="Task", icon="code", url="/task"),
            # rx.divider(margin_y="0.5em"),
            # rx.text(
            #     "历史对话",
            #     font_weight="bold",
            #     padding_left="0.75em",
            #     margin_bottom="0.5em",
            # ),
            align_items="stretch",
            spacing="2",
        ),
        width="12em",
        height="100%",
        padding="0.5em",
        background_color=rx.color("mauve", 3),
        top="auto",
        left="auto",
        spacing="2",
        margin_top="0em",
    )
