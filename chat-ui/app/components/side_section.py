# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

from typing import List, cast

import reflex as rx

from app.states.state import FunctionMenu


def sidebar_item(item: FunctionMenu) -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.hstack(
                    rx.icon(item.icon, margin_right="0.5em"),
                    rx.text(item.title),
                    width="100%",
                    # justify_content="flex-start",
                ),
                on_click=rx.redirect(item.tobe),
                variant="soft",
                # 默认背景色
                background_color=rx.color("mauve", 5),
                # 鼠标悬停时的背景色
                _hover={
                    "background_color": rx.color("mauve", 2),  # 悬停时颜色加深
                    "color": rx.color("mauve", 10),  # 可选：悬停时文字颜色变化
                    "transition": "all 0.1s ease",  # 平滑过渡效果
                },
                display="flex",
                justify_content="center",
                align_items="center",
                height="5em",
                width="100%",
            ),
        ),
        rx.cond(
            item.children,
            rx.menu.content(
                rx.foreach(cast(List[FunctionMenu], item.children), sidebar_item_child)
            ),
        ),
        width="100%",
    )


def sidebar_item_child(child_item: FunctionMenu) -> rx.Component:
    """侧边栏子菜单项组件"""
    return rx.menu.item(
        rx.hstack(
            rx.icon(child_item.icon, margin_right="0.5em"),
            rx.text(child_item.title, font_size="1.2em"),
            _hover={
                "background_color": rx.color("mauve", 3),
                "transition": "all 0.1s ease",
            },
            width="100%",
        ),
        width="15em",
        display="flex",
        justify_content="center",
        align_items="center",
        height="3em",
        on_click=rx.redirect(child_item.tobe),
    )


def sidebar(State) -> rx.Component:
    return rx.box(
        # 侧边栏内容
        rx.vstack(
            # 品牌标识区域
            rx.hstack(
                rx.avatar(name="NovaAI", src="../novaai.png"),
                rx.text("NovaAI", size="6", weight="bold"),
                justify_content="center",
                align_items="center",
                margin_bottom="0.5em",
            ),
            rx.divider(),
            # 功能菜单区域
            rx.vstack(
                rx.text(
                    "AI Menu",
                    size="3",
                    weight="bold",
                    padding_left="0.25em",
                    margin_top="0.5em",
                ),
                rx.foreach(State.function_menu, lambda item: sidebar_item(item)),
                align_items="stretch",
                spacing="2",
                width="100%",
            ),
            spacing="0",
            width="100%",
            height="100%",
        ),
        # # 动态宽度：展开时15em，收起时4em
        width=rx.cond(State.sidebar_visible, "15em", "0"),
        opacity=rx.cond(State.sidebar_visible, "1", "0"),
        height="100%",
        padding=rx.cond(State.sidebar_visible, "0.5em", "0"),
        background_color=rx.color("mauve", 3),
        transition="all 0.3s ease",  # 平滑过渡动画
        overflow="hidden",  # 防止内容溢出
        z_index="5",
    )
