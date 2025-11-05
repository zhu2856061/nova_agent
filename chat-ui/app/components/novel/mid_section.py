# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from typing import List, Optional

import reflex as rx


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


# 2. 定义标签项模型（支持动态配置）--------------------------
class TabItem(rx.Base):
    """标签项数据模型"""

    value: str  # 标签唯一标识（用于切换）
    label: str  # 标签显示文本
    content: rx.Component  # 标签对应的内容组件（延迟渲染）
    disabled: bool = False  # 是否禁用标签
    icon: Optional[str] = None  # 标签图标（可选）


# 3. 生成标签触发按钮（统一样式）--------------------------
def tab_trigger(tab: TabItem, state: rx.State) -> rx.Component:
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
def tab_content(tab: TabItem) -> rx.Component:
    """生成标签内容区（支持自定义组件）"""
    return rx.tabs.content(
        # 内容容器（添加样式优化）
        rx.box(
            tab.content,  # 执行content函数渲染内容（延迟加载）
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


# 5. 示例：标签内容组件（需根据实际业务实现）--------------------------
def chat_component(state) -> rx.Component:
    """聊天交互标签内容（复用之前优化的chat组件）"""

    return rx.text("小说编辑器", font_size="1.5em", weight="bold", margin_bottom="1em")


def editor_component(state) -> rx.Component:
    """小说编辑标签内容（示例实现）"""
    return rx.vstack(
        rx.text("小说编辑器", font_size="1.5em", weight="bold", margin_bottom="1em"),
        rx.text_area(
            placeholder="在这里编辑小说内容...",
            value="state.novel_content",
            width="100%",
            height="25em",
            border_radius="8px",
            border=f"1px solid {NovelWorkspaceStyle.BORDER_COLOR}",
            padding="1em",
            font_size="1.05em",
            resize="vertical",
        ),
        rx.button(
            "保存内容",
            # on_click=state.save_novel_content,
            background_color=rx.color("accent", 6),
            _hover={"background_color": rx.color("accent", 7)},
            margin_top="1em",
        ),
        width="100%",
        height="100%",
        align_items="flex-start",
        gap="1em",
    )


def settings_component(state) -> rx.Component:
    """设置标签内容（示例实现）"""
    return rx.vstack(
        rx.text("工作区设置", font_size="1.5em", weight="bold", margin_bottom="1.5em"),
        rx.box(
            rx.text("主题颜色："),
            rx.select(
                ["默认（Mauve）", "蓝色（Blue）", "绿色（Green）", "深色（Dark）"],
                value="蓝色（Blue）",
                width="20em",
                margin_top="0.5em",
            ),
            margin_bottom="1.5em",
        ),
        width="100%",
        height="100%",
        align_items="flex-start",
        gap="1em",
    )


# 6. 工作区主组件（核心逻辑）--------------------------
def novel_workspace(state) -> rx.Component:
    """小说工作区（优化后的垂直标签页组件）"""
    # 1. 定义标签列表（可动态从state读取，此处示例静态配置）
    tabs: List[TabItem] = [
        TabItem(
            value="chat",
            label="聊天交互",
            icon="message-square",  # 图标（Reflex内置图标名）
            content=chat_component(state),  # 聊天组件（需实现）
        ),
        TabItem(
            value="novel_editor",
            label="小说编辑",
            icon="edit-3",
            content=editor_component(state),  # 编辑器组件（需实现）
        ),
        TabItem(
            value="settings",
            label="设置",
            icon="settings",
            disabled=False,  # 可设置为True禁用标签
            content=settings_component(state),  # 设置组件（需实现）
        ),
    ]

    return rx.tabs.root(
        # 标签列表（垂直布局）
        rx.tabs.list(
            rx.foreach(tabs, lambda tab: tab_trigger(tab, state)),
            width=NovelWorkspaceStyle.TABS_LIST_WIDTH,
            height=NovelWorkspaceStyle.TABS_LIST_HEIGHT,
            background_color=NovelWorkspaceStyle.TABS_LIST_BG,
            border_radius=NovelWorkspaceStyle.BORDER_RADIUS,
            padding="0.5em",
            gap="1.5em",
            flex_direction="column",  # 垂直排列
        ),
        # 标签内容区
        rx.foreach(tabs, tab_content),
        # rx.box(
        #     rx.foreach(tabs, tab_content),
        #     flex="1",  # 占满剩余宽度
        #     padding="0.8em",
        # ),
        # 标签页核心配置
        default_value="chat",  # 默认选中第一个标签
        # value=state.current_chat,  # 关联状态（同步选中标签）
        # on_change=rx.set_value(state, "current_chat"),  # 标签切换时更新状态
        orientation="vertical",  # 垂直布局
        width=NovelWorkspaceStyle.TABS_ROOT_WIDTH,
        height="100%",
        display="flex",
        gap="0.5em",
    )
