# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx
from app.components.novel.core_interact_section import (
    editor_component_form,
    settings_component,
)
from app.states.interact_ainovel_state import NovelStepMenu


# 1. 提取样式常量（统一维护）--------------------------
class NovelWorkspaceStyle:
    """小说工作区标签页样式常量"""

    # 尺寸相关
    TABS_ROOT_WIDTH = "100%"  # 标签页根容器宽度
    TABS_LIST_WIDTH = "12em"  # 垂直布局时标签列表宽度
    TABS_LIST_HEIGHT = "100%"  # 垂直布局时标签列表高度
    TABS_CONTENT_PADDING = "1.5em"  # 内容区内边距
    TRIGGER_HEIGHT = "3.2em"  # 标签触发按钮高度
    TRIGGER_FONT_SIZE = "1.0em"  # 标签文字大小

    # 颜色相关
    TABS_LIST_BG = rx.color("mauve", 2)  # 标签列表背景色
    TRIGGER_HOVER_BG = rx.color("mauve", 5)  # 标签悬浮背景色
    TRIGGER_ACTIVE_BG = rx.color("mauve", 5)  # 标签选中背景色
    TEXT_COLOR = rx.color("mauve", 12)  # 文字颜色
    BORDER_COLOR = rx.color("mauve", 4)  # 边框颜色
    # 样式相关
    BORDER_RADIUS = "5px"  # 全局圆角
    TRIGGER_BORDER_RADIUS = "5px"  # 标签按钮圆角
    BOX_SHADOW = "0 2px 10px rgba(0,0,0,0.05)"  # 轻微阴影（提升层次感）
    TRANSITION_DURATION = "0.2s"  # 过渡动画时长


# 3. 生成标签触发按钮（统一样式）--------------------------
def tab_trigger(tab: NovelStepMenu) -> rx.Component:
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
        height=NovelWorkspaceStyle.TRIGGER_HEIGHT,
        font_size=NovelWorkspaceStyle.TRIGGER_FONT_SIZE,
        _hover={
            "background_color": NovelWorkspaceStyle.TRIGGER_HOVER_BG,
            "transition": "background-color 0.2s ease",
        },
        width="100%",
        display="flex",
        align_items="center",
        justify_content="flex-start",
        border_radius=NovelWorkspaceStyle.TRIGGER_BORDER_RADIUS,
    )


# 4. 生成标签内容（延迟渲染）--------------------------
def tab_content(tab: NovelStepMenu, state) -> rx.Component:
    """生成标签内容区（支持自定义组件）"""
    return rx.tabs.content(
        # 内容容器（添加样式优化）
        rx.box(
            rx.cond(
                tab.content == "editor",
                editor_component_form(tab, state),
                rx.cond(
                    tab.content == "settings",
                    settings_component(tab, state),
                    rx.box(),  # 无内容时占位，避免布局抖动
                ),
            ),
            width="100%",
            height="100%",
            min_height="30em",  # 最小高度（避免内容过短时布局塌陷）
            border_radius=NovelWorkspaceStyle.BORDER_RADIUS,
            box_shadow=NovelWorkspaceStyle.BOX_SHADOW,
            padding=NovelWorkspaceStyle.TABS_CONTENT_PADDING,
            overflow="auto",  # 内容超出时滚动
        ),
        value=tab.value,
        width="100%",
        height="100%",
    )


# 6. 工作区主组件（核心逻辑）--------------------------
def novel_workspace(state) -> rx.Component:
    """小说工作区（优化后的垂直标签页组件）"""
    # 1. 定义标签列表（可动态从state读取，此处示例静态配置）
    return rx.tabs.root(
        # 标签列表（垂直布局）
        rx.tabs.list(
            rx.foreach(state.novel_tabs, tab_trigger),
            width=NovelWorkspaceStyle.TABS_LIST_WIDTH,
            height=NovelWorkspaceStyle.TABS_LIST_HEIGHT,
            background_color=NovelWorkspaceStyle.TABS_LIST_BG,
            border_radius=NovelWorkspaceStyle.BORDER_RADIUS,
            padding="0.5em",
            gap="1.5em",
            flex_direction="column",  # 垂直排列
        ),
        # 标签内容区
        rx.foreach(state.novel_tabs, lambda _: tab_content(_, state)),
        # rx.box(
        #     rx.foreach(tabs, tab_content),
        #     flex="1",  # 占满剩余宽度
        #     padding="0.8em",
        # ),
        on_change=state.change_tab_value,
        # 标签页核心配置
        default_value=state.current_tab,  # 默认选中第一个标签
        orientation="vertical",  # 垂直布局
        width=NovelWorkspaceStyle.TABS_ROOT_WIDTH,
        height="100%",
        display="flex",
        gap="0.5em",
    )
