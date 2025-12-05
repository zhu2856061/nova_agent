# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from typing import List, Union

import reflex as rx
from app.components.common.head_components import headbar
from app.components.common.sidebar_components import SideMenu, sidebar
from app.components.common.tailbar_components import footer


def basic_page(
    brand: Union[rx.Var[str], str],
    logo: Union[rx.Var[str], str],
    menu: List[SideMenu],
    badge: Union[rx.Var[str], str],
    main_compoent: rx.Component,
) -> rx.Component:
    return rx.hstack(
        sidebar(brand, logo, menu),
        rx.vstack(
            headbar(badge),
            # # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
            # # 这一行是触发同步的“钩子”，必须加！
            # rx.box(
            #     on_mount=ChatState.init_chat_state,  # 页面加载时执行一次
            #     display="none",  # 完全隐藏，不影响布局
            # ),
            # # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
            rx.box(
                main_compoent,
                flex="1",  # 自动填充剩余高度
                overflow_y="auto",  # 消息过多时局部滚动
                overflow_x="hidden",
                padding_bottom="10px",  # 为tailbar预留80px空间（根据tailbar高度调整）
            ),
            # 底部固定区：包含操作栏和页脚，避免粘性定位冲突
            footer(),
            # 主内容区样式优化
            background_color=rx.color("mauve", 1),
            color=rx.color("mauve", 12),
            height="100%",
            width="100%",
            align_items="stretch",
            spacing="0",
            # 关键：弹性布局分配高度，聊天区自动填充剩余空间
            flex="1",
            display="flex",
            flex_direction="column",
            # 防止主内容区溢出
            overflow="hidden",
        ),
        # 外层水平容器样式
        background_color=rx.color("mauve", 1),
        color=rx.color("mauve", 12),
        spacing="0",
        width="100%",
        height="100dvh",
        # 关键：让 hstack 子组件按弹性布局分配宽度，避免侧边栏挤压主内容区
        align_items="stretch",
    )
