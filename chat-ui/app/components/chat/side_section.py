# # -*- coding: utf-8 -*-
# # @Time   : 2025/09/24 10:24
# # @Author : zip
# # @Moto   : Knowledge comes from decomposition

from typing import List, cast

import reflex as rx
from app.states.state import FunctionMenu


# -------------------------- 1. 提取常量（统一维护，便于修改）--------------------------
class SidebarStyle:
    """侧边栏样式常量"""

    # 尺寸相关
    EXPANDED_WIDTH = "16em"  # 展开宽度（比原15em更宽松）
    COLLAPSED_WIDTH = "0"  # 收起宽度（保留图标，而非完全隐藏）
    BRAND_MARGIN_BOTTOM = "1.5em"  # 品牌区底部间距（原0.5em太拥挤）
    BRAND_FONT_SIZE = "6"  # 品牌名称字体大小
    ICON_CONTAINER_SIZE = "2rem"  # 图标容器固定尺寸（适配16px图标，留足边距）
    ICON_FIXED_SIZE = 24  # 图标固定大小（不再随父容器变化）

    CHILD_ICON_CONTAINER_SIZE = "1rem"  # 图标容器固定尺寸（适配16px图标，留足边距）
    CHILD_ICON_FIXED_SIZE = 12  # 图标固定大小（不再随父容器变化）

    # 颜色相关
    BACKGROUND_COLOR = rx.color("mauve", 3)  # 侧边栏背景色
    TEXT_COLOR = rx.color("mauve", 12)  # 文字颜色（深色，提升可读性）

    # 间距相关
    PADDING_EXPANDED = "0.8em"  # 展开时内边距
    PADDING_COLLAPSED = "0.5em"  # 收起时内边距

    # 动画相关
    TRANSITION_DURATION = "0.3s"  # 过渡动画时长


def accordion_item(item: FunctionMenu) -> rx.Component:
    return rx.accordion.item(
        header=rx.hstack(
            rx.box(
                rx.icon(
                    item.icon,
                    size=SidebarStyle.ICON_FIXED_SIZE,
                    color=rx.color("mauve", 8),
                ),
                width=SidebarStyle.ICON_CONTAINER_SIZE,
                height=SidebarStyle.ICON_CONTAINER_SIZE,
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink="0",
            ),
            rx.text(
                item.title,
                font_size="1.2em",
                color=SidebarStyle.TEXT_COLOR,
            ),
            width="100%",
            align_items="center",
        ),
        content=rx.vstack(
            rx.foreach(cast(List[FunctionMenu], item.children), accordion_item_child)
        ),
        value=item.title,
        background_color=rx.color("mauve", 5),
    )


def accordion_item_child(child_item: FunctionMenu) -> rx.Component:
    """侧边栏子菜单项组件"""
    return rx.button(
        rx.box(
            rx.icon(
                child_item.icon,
                size=SidebarStyle.CHILD_ICON_FIXED_SIZE,
                color=rx.color("mauve", 8),
            ),
            width=SidebarStyle.CHILD_ICON_CONTAINER_SIZE,
            height=SidebarStyle.CHILD_ICON_CONTAINER_SIZE,
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.text(child_item.title, font_size="1.0em"),
        _hover={
            "background_color": rx.color("mauve", 3),
            "transition": "all 0.1s ease",
        },
        width="100%",
        display="flex",
        justify_content="left",
        align_items="center",
        height="3em",
        on_click=rx.redirect(child_item.tobe),
    )


# -------------------------- 5. 侧边栏主组件（优化显隐逻辑、响应式）--------------------------
def sidebar(state) -> rx.Component:
    """侧边栏主组件（支持展开/收起，优化交互体验）"""
    return rx.box(
        rx.vstack(
            # 品牌标识区域（优化图片路径、样式）
            rx.hstack(
                # 修复图片路径：Reflex静态资源需放在assets文件夹，路径直接写文件名
                rx.avatar(
                    name="NovaAI",
                    src="../novaai.png",  # 假设图片放在assets/novaai.png
                    border_radius="8px",
                ),
                # 展开时显示品牌名称，收起时隐藏
                rx.text("NovaAI", size=SidebarStyle.BRAND_FONT_SIZE, weight="bold"),
                justify_content="center",
                align_items="center",
                margin_bottom=SidebarStyle.BRAND_MARGIN_BOTTOM,
                width="100%",
            ),
            # 功能菜单区域（优化折叠面板样式）
            rx.scroll_area(
                rx.accordion.root(
                    rx.foreach(state.function_menu, lambda item: accordion_item(item)),
                    collapsible=True,
                    type="multiple",
                    width="100%",
                    style={"--accordion-border-width": "0px"},
                ),
                height="calc(100% - 8em)",  # 减去品牌区高度，避免滚动区域溢出
                width="100%",
            ),
            # rx.accordion.root(
            #     rx.foreach(state.function_menu, lambda item: accordion_item(item)),
            #     collapsible=True,
            #     type="multiple",
            #     width="100%",
            #     align_items="stretch",
            #     # 折叠面板边框移除，更美观
            #     style={"--accordion-border-width": "0px"},
            # ),
            width="100%",
            height="100%",
            justify_content="flex-start",  # 内容顶部对齐
            gap="0.3em",  # 菜单之间间距
        ),
        # 动态样式（展开/收起切换）
        width=rx.cond(
            state.sidebar_visible,
            SidebarStyle.EXPANDED_WIDTH,
            SidebarStyle.COLLAPSED_WIDTH,
        ),
        height="100vh",
        # 固定定位（如果需要侧边栏不随页面滚动）
        position="sticky",
        top="0",
        opacity=rx.cond(state.sidebar_visible, 1, 0),  # 收起时轻微透明，不完全隐藏
        display="flex",
        padding=rx.cond(
            state.sidebar_visible,
            SidebarStyle.PADDING_EXPANDED,
            SidebarStyle.PADDING_COLLAPSED,
        ),
        background_color=SidebarStyle.BACKGROUND_COLOR,
        transition=f"width {SidebarStyle.TRANSITION_DURATION} ease, padding {SidebarStyle.TRANSITION_DURATION} ease, opacity {SidebarStyle.TRANSITION_DURATION} ease",
        overflow="hidden",
        z_index="10",  # 提升层级，确保不被遮挡
        box_shadow="0 0 10px rgba(0,0,0,0.05)",  # 轻微阴影，提升层次感
        border_radius="0 8px 8px 0",  # 右侧圆角（如果侧边栏在左侧）
    )
