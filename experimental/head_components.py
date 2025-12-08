# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Any, Callable

import reflex as rx


class HeaderBarState(rx.State):
    is_settings_modal_open: bool = False
    is_create_chat_modal_open: bool = False
    badge = ""
    title = ""
    _shared = None

    def init_header_bar_state(self, shared):
        """初始化状态"""
        self.is_settings_modal_open = False
        self.is_create_chat_modal_open = False
        self.badge = ""
        self.title = ""
        self._shared = shared

    # 设置徽章
    @rx.event
    def set_badge(self, name: str):
        self.badge = name

    # 设置创建聊天的模态框的标题
    @rx.event
    def set_title(self, name: str):
        self.title = name

    # 创建新聊天的模态框开关
    @rx.event
    def set_is_create_chat_modal_open(self, is_open: bool):
        self.is_create_chat_modal_open = is_open

    # 设置参数值的模态框开关
    @rx.event
    def set_is_settings_modal_open(self, is_open: bool):
        self.is_settings_modal_open = is_open

    # 创建会话窗口的提交事件
    @rx.event
    async def create_workspace(self, form_data: dict[str, Any]):
        _name = form_data["new_chat_name"]
        if self._shared:
            self._shared.create_workspace(_name)

    # 设置当前工作区
    @rx.event
    async def set_workspace(self, name: str):
        if self._shared:
            self._shared.set_workspace(name)

    # 删除当前工作区
    @rx.event
    async def del_workspace(self, name: str):
        if self._shared:
            self._shared.del_workspace(name)

    # 获得所有会话窗口名称
    @rx.var
    async def get_workspace_names(self) -> list[str]:
        if self._shared:
            return self._shared.get_workspace_names()
        return []


def chat_menu(chat: str) -> rx.Component:
    """侧边栏中的单个聊天项组件"""
    # 返回一个抽屉关闭组件，点击该组件会关闭抽屉
    return rx.drawer.close(
        # 使用水平堆叠布局放置聊天按钮和删除按钮
        rx.hstack(
            # 聊天标题按钮，点击时设置当前聊天
            rx.button(
                chat,  # 显示聊天标题
                on_click=lambda: HeaderBarState.set_workspace(chat),
                width="80%",  # 占父容器80%宽度
                variant="surface",  # 使用表面样式的按钮变体
            ),
            # 删除按钮，用于删除当前聊天项
            rx.button(
                # 垃圾桶图标作为按钮内容
                rx.icon(
                    tag="trash",  # 使用垃圾桶图标
                    on_click=lambda: HeaderBarState.del_workspace(
                        chat
                    ),  # 点击时删除该聊天
                    stroke_width=1,  # 图标线条宽度
                ),
                width="20%",  # 占父容器20%宽度
                variant="surface",  # 使用表面样式的按钮变体
                color_scheme="red",  # 使用红色配色方案，暗示删除操作
            ),
            width="100%",  # 水平堆叠占满父容器宽度
        ),
        key=chat,  # 为每个聊天项设置唯一key，用于React渲染优化
    )


def chat_drawer(trigger) -> rx.Component:
    """侧边栏组件，用于显示所有聊天项列表"""
    # 返回一个抽屉根组件
    return rx.drawer.root(
        rx.drawer.trigger(trigger),  # 抽屉触发器，传入的参数作为触发元素
        rx.drawer.overlay(),  # 抽屉的遮罩层
        rx.drawer.portal(  # 抽屉的门户容器，用于将抽屉渲染到DOM的其他位置
            rx.drawer.content(  # 抽屉的内容区域
                # 垂直堆叠布局，用于排列标题、分隔线和聊天列表
                rx.vstack(
                    rx.heading(
                        HeaderBarState.title, color=rx.color("mauve", 11)
                    ),  # 侧边栏标题
                    rx.divider(),  # 分隔线
                    # 遍历状态中的所有聊天标题，为每个创建一个sidebar_chat组件
                    rx.foreach(
                        HeaderBarState.get_workspace_names, lambda _: chat_menu(_)
                    ),
                    align_items="stretch",  # 子元素拉伸填满宽度
                    width="100%",  # 占满父容器宽度
                ),
                top="auto",  # 不固定顶部位置
                left="auto",
                height="100%",  # 高度占满屏幕
                width="20em",  # 宽度为20em
                padding="2em",  # 内边距2em
                background_color=rx.color(
                    "mauve", 2
                ),  # 使用mauve色系的第2种颜色作为背景
                outline="none",  # 移除轮廓线
            )
        ),
        direction="right",  # 抽屉从左侧滑出
    )


def create_chat_modal(
    trigger: rx.Component,
    title: str,
    create_chat: Callable,
) -> rx.Component:
    """用于创建新聊天的模态框组件"""
    return rx.dialog.root(  # 对话框根组件
        rx.dialog.trigger(trigger),  # 对话框触发器，传入的参数作为触发元素
        rx.dialog.content(  # 对话框内容区域
            # 表单组件，用于输入新聊天名称
            rx.form(
                # 水平堆叠布局，放置输入框和创建按钮
                rx.hstack(
                    rx.input(  # 输入框，用于输入新聊天名称
                        placeholder=f"{title} name",  # 占位文本
                        name="new_chat_name",  # 表单字段名称
                        flex="1",  # 弹性布局，占满可用空间
                        min_width="20ch",  # 最小宽度为20个字符
                    ),
                    rx.button(f"Create {title}"),  # 创建聊天按钮
                    spacing="2",  # 子元素间距
                    wrap="wrap",  # 超出时自动换行
                    width="100%",  # 占满父容器宽度
                ),
                on_submit=[
                    create_chat,
                    HeaderBarState.set_is_create_chat_modal_open(False),
                ],
                reset_on_submit=True,
            ),
            background_color=rx.color("mauve", 1),  # 使用mauve色系的第1种颜色作为背景
        ),
        open=HeaderBarState.is_create_chat_modal_open,  # 控制模态框是否打开的状态
        on_open_change=HeaderBarState.set_is_create_chat_modal_open,  # 模态框打开状态变化时调用的方法
    )


def headbar(badge) -> rx.Component:
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
        # 右侧区域：展示 + 保存按钮（固定靠右）
        rx.hstack(
            # 创建新聊天的模态框，使用消息加号图标作为触发器
            create_chat_modal(
                rx.icon_button("message-square-plus"),
                HeaderBarState.title,
                HeaderBarState.create_workspace.stop_propagation(),
            ),
            # 侧边栏组件，使用消息图标作为触发器
            chat_drawer(
                rx.icon_button("messages-square", background_color=rx.color("mauve", 6))
            ),
            # 核心：靠右对齐 + 移除居中margin
            justify_content="flex-end",  # 子元素整体靠右
            align_items="center",  # 垂直居中（保留）
            width="100%",  # 占满父容器宽度（必须，否则靠右无效）
            gap="8px",  # 图标和按钮之间的间距（可选，更美观）
            margin_top="5px",
            spacing="2",
        ),
        align_items="right",  # 子元素垂直居中
        padding="12px",  # 内边距12px
        border_bottom=f"1px solid {rx.color('mauve', 3)}",  # 底部边框，使用mauve色系的第3种颜色
        background_color=rx.color("mauve", 2),  # 使用mauve色系的第2种颜色作为背景
    )
