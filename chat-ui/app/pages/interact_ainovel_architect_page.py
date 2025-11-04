# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx

from app.components import novel_footer, novel_headbar, sidebar
from app.states.interact_ainovel_state import InteractAiNovelState


# 1. 定义页面组件函数，返回Reflex组件（rx.Component）
def interact_ainovel_architect_page() -> rx.Component:
    # 2. 根布局：水平堆叠容器（rx.hstack），用于并列放置「侧边栏」和「主内容区」
    return rx.hstack(
        # 3. 左侧侧边栏：调用自定义组件sidebar，传入状态管理类InteractAiNovelState（用于状态共享）
        sidebar(InteractAiNovelState),
        # 4. 右侧主内容区：垂直堆叠容器（rx.vstack），用于垂直排列「导航栏」和「页脚」
        rx.vstack(
            # 5. 主内容区顶部：导航栏组件，同样传入状态类（状态透传）
            novel_headbar(InteractAiNovelState),
            # rx.box(
            #     # 这里放小说内容组件
            #     overflow="auto",  # 超出部分滚动
            #     flex_grow=1,  # 占满vstack剩余高度
            # ),
            # 6. 主内容区底部：页脚组件（当前需要固定在最下方）
            novel_footer(InteractAiNovelState),
            # 7. 主内容区（rx.vstack）样式配置
            background_color=rx.color(
                "mauve", 1
            ),  # 背景色：mauve（淡紫色）色系1号（浅淡）
            color=rx.color("mauve", 12),  # 文字颜色：mauve色系12号（深浓）
            height="100%",  # 高度占满父容器（rx.hstack）的100%
            width="100%",  # 宽度占满父容器的100%
            align_items="stretch",  # 子组件横向拉伸（占满vstack宽度）
            spacing="0",  # 子组件（导航栏+页脚）之间无间距
            display="flex",
            justify_content="space-between",
        ),
        background_color=rx.color(
            "mauve", 1
        ),  # 整体页面背景色（与主内容区一致，视觉统一）
        color=rx.color("mauve", 12),  # 全局默认文字颜色
        align_items="stretch",  # 子组件（侧边栏+主内容区）纵向拉伸（占满hstack高度）
        spacing="0",  # 侧边栏和主内容区之间无间距
        height="100dvh",  # 根布局高度=视口高度（100dvh，屏幕可见区域100%）
    )
