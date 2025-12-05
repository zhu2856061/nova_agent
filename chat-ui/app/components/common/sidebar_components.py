# # -*- coding: utf-8 -*-
# # @Time   : 2025/09/24 10:24
# # @Author : zip
# # @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import List, Optional, Union, cast

import reflex as rx


class SideMenu(rx.Model):
    title: str
    icon: str
    tobe: str = "/"
    children: Optional[List["SideMenu"]] = None


class SideState(rx.State):
    brand = "NovaAI"
    logo = "../novaai.png"

    menu: List[SideMenu] = [
        SideMenu(
            title="Chat",
            icon="message-circle-more",
            children=[
                SideMenu(
                    title="llm",
                    icon="message-circle-more",
                    tobe="/chat/llm",
                ),
            ],
        ),
        SideMenu(
            title="Agent",
            icon="bot-message-square",
            children=[
                SideMenu(
                    title="memorizer",
                    icon="bot-message-square",
                    tobe="/agent/memorizer",
                ),
                SideMenu(
                    title="themeslicer",
                    icon="bot-message-square",
                    tobe="/agent/themeslicer",
                ),
                SideMenu(
                    title="web_searcher",
                    icon="bot-message-square",
                    tobe="/agent/researcher",
                ),
                SideMenu(
                    title="wechat_searcher",
                    icon="bot-message-square",
                    tobe="/agent/wechat_researcher",
                ),
                SideMenu(
                    title="deepresearcher",
                    icon="clipboard-list",
                    tobe="/task/deepresearcher",
                ),
                SideMenu(
                    title="ainovel",
                    icon="clipboard-list",
                    tobe="/task/ainovel",
                ),
                SideMenu(
                    title="ainovel_architect",
                    icon="bot-message-square",
                    tobe="/agent/ainovel_architect",
                ),
                SideMenu(
                    title="ainovel_chapter",
                    icon="bot-message-square",
                    tobe="/agent/ainovel_chapter",
                ),
            ],
        ),
        SideMenu(
            title="Interact",
            icon="layout-dashboard",
            children=[
                SideMenu(
                    title="ainovel",
                    icon="layout-dashboard",
                    tobe="/interact/ainovel",
                ),
            ],
        ),
    ]

    visible: bool = True  # 侧边栏是否展开

    @rx.event
    def toggle_sidebar(self):
        """切换侧边栏展开/收起状态"""
        self.visible = not self.visible


def accordion_item(item: SideMenu) -> rx.Component:
    return rx.accordion.item(
        header=rx.hstack(
            rx.box(
                rx.icon(item.icon, size=24, color=rx.color("mauve", 8)),
                width="2rem",  # 图标容器固定尺寸（适配16px图标，留足边距）
                height="2rem",
                display="flex",
                align_items="center",
                justify_content="center",
            ),
            # 文本在收起时隐藏，添加过渡动画
            rx.text(
                item.title,
                font_size="1.2em",
                color=rx.color("mauve", 12),
            ),
            width="100%",
            align_items="center",
            padding_x="0.5em",
        ),
        content=rx.vstack(
            rx.foreach(cast(List[SideMenu], item.children), accordion_item_child)
        ),
        value=item.title,
        background_color=rx.color("mauve", 5),
    )


def accordion_item_child(child_item: SideMenu) -> rx.Component:
    """侧边栏子菜单项组件"""
    return rx.button(
        rx.box(
            rx.icon(child_item.icon, size=12, color=rx.color("mauve", 8)),
            width="1rem",
            height="1rem",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        rx.text(child_item.title, font_size="1.0em"),
        _hover={"background_color": rx.color("mauve", 3)},
        width="100%",
        display="flex",
        justify_content="left",
        align_items="center",
        height="3em",
        padding_x="1em",  # 增加内边距，提升点击体验
        on_click=rx.redirect(child_item.tobe),
    )


# -------------------------- 5. 侧边栏主组件（优化显隐逻辑、响应式）--------------------------
def sidebar(
    brand: Union[rx.Var[str], str], logo: Union[rx.Var[str], str], menu: List[SideMenu]
) -> rx.Component:
    return rx.box(
        # 外层容器：相对定位，作为Logo和箭头的定位参考
        rx.box(
            # 1. 顶部固定Logo：始终显示（展开/收起都有）
            rx.avatar(
                name=brand,
                src=logo,
                border_radius="8px",
                size="3",  # 收起时Logo尺寸
                # 绝对定位固定在顶部
                position="absolute",
                top="1em",  # 距离顶部1em
                left="50%",  # 水平居中
                transform="translateX(-50%)",
                z_index="11",  # 确保Logo在最上层
                # 展开时隐藏这个独立的Logo（因为主体里会显示带文字的Logo）
                display=rx.cond(SideState.visible, "none", "block"),
            ),
            # 2. 主体内容：仅展开时显示（Logo+品牌文字+菜单）
            rx.vstack(
                # 展开时：Logo与品牌文字横向并排
                rx.hstack(
                    rx.avatar(
                        name=brand,
                        src=logo,
                        border_radius="8px",
                        size="3",
                    ),
                    rx.text(brand, size="6", weight="bold"),
                    justify_content="center",
                    align_items="center",
                    margin_top="0.5em",
                    margin_bottom="0.5em",
                    width="100%",
                ),
                # 菜单区域
                rx.scroll_area(
                    rx.accordion.root(
                        rx.foreach(menu, accordion_item),
                        collapsible=True,
                        type="multiple",
                        width="100%",
                        style={
                            "--accordion-border-width": "0px",
                            "--accordion-item-gap": "0.2em",
                        },  # 缩小面板间距
                    ),
                    width="100%",
                    flex_grow="1",
                    max_height="calc(100vh - 4em)",  # 限制最大高度（视口高度 - 顶部/底部预留空间）
                    style={
                        "overflow-y": "auto",
                        "overflow-x": "hidden",
                        # "padding_right": "0.5em",  # 为滚动条预留空间
                    },
                ),
                # 外层容器样式：禁止自身滚动
                # width=rx.cond(SideState.visible, "24em", "4rem"),
                width="100%",
                height="100%",
                justify_content="flex-start",
                gap="0",  # 取消间距，避免额外高度
                # 关键：为底部箭头预留6em的固定空间，避免滚动区域重叠
                padding_bottom="4em",
                # 展开显示/收起隐藏
                display=rx.cond(SideState.visible, "flex", "none"),
            ),
            # 3. 底部固定箭头：始终显示（展开左箭头/收起右箭头）
            rx.icon_button(
                rx.cond(
                    SideState.visible,
                    rx.icon("circle-chevron-left", size=30),  # 展开显示左箭头
                    rx.icon("circle-chevron-right", size=30),  # 收起显示右箭头
                ),
                variant="ghost",
                size="1",
                on_click=SideState.toggle_sidebar,
                color=rx.color("mauve", 10),
                _hover={"background_color": rx.color("mauve", 4)},
                # 绝对定位固定在底部
                position="absolute",
                bottom="0.8em",  # 距离底部1em
                left="50%",  # 水平居中
                transform="translateX(-50%)",
                z_index="11",  # 确保箭头在最上层
            ),
            width="100%",
            height="100%",
            position="relative",  # 必须：作为内部绝对定位的参考
            overflow="hidden",  # 关键：外层侧边栏不滚动，仅内部scroll_area滚动
        ),
        # 动态宽度：展开16em，收起4rem（容纳Logo+箭头）
        width=rx.cond(SideState.visible, "14em", "4rem"),
        height="100vh",  # 占满视口高度
        position="sticky",
        top="0",
        background_color=rx.color("mauve", 3),
        transition="width 0.3s ease",  # 平滑宽度过渡
        overflow="hidden",
        z_index="10",
        box_shadow="0 0 10px rgba(0,0,0,0.05)",
        border_radius="0 8px 8px 0",
    )
