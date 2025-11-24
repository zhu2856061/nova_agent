# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Any, Callable, List, Optional

import reflex as rx


class Parameters(rx.Model):
    mkey: str
    mvalue: Any
    mtype: str = "text"
    mvaluetype: str
    mselected: Optional[List[Any]] = None


class InputBarState(rx.State):
    is_settings_modal_open: bool = False
    is_create_chat_modal_open: bool = False

    # 设置参数值的模态框开关
    @rx.event
    def set_is_settings_modal_open(self, is_open: bool):
        self.is_settings_modal_open = is_open

    # 创建新聊天的模态框开关
    @rx.event
    def set_is_create_chat_modal_open(self, is_open: bool):
        self.is_create_chat_modal_open = is_open


def chat_menu(chat: str, set_chat_name, del_chat_name) -> rx.Component:
    """侧边栏中的单个聊天项组件"""
    # 返回一个抽屉关闭组件，点击该组件会关闭抽屉
    return rx.drawer.close(
        # 使用水平堆叠布局放置聊天按钮和删除按钮
        rx.hstack(
            # 聊天标题按钮，点击时设置当前聊天
            rx.button(
                chat,  # 显示聊天标题
                on_click=lambda: set_chat_name(chat),
                width="80%",  # 占父容器80%宽度
                variant="surface",  # 使用表面样式的按钮变体
            ),
            # 删除按钮，用于删除当前聊天项
            rx.button(
                # 垃圾桶图标作为按钮内容
                rx.icon(
                    tag="trash",  # 使用垃圾桶图标
                    on_click=lambda: del_chat_name(chat),  # 点击时删除该聊天
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


def chat_drawer(
    trigger, title, chat_names, set_chat_name, del_chat_name
) -> rx.Component:
    """侧边栏组件，用于显示所有聊天项列表"""
    # 返回一个抽屉根组件
    return rx.drawer.root(
        rx.drawer.trigger(trigger),  # 抽屉触发器，传入的参数作为触发元素
        rx.drawer.overlay(),  # 抽屉的遮罩层
        rx.drawer.portal(  # 抽屉的门户容器，用于将抽屉渲染到DOM的其他位置
            rx.drawer.content(  # 抽屉的内容区域
                # 垂直堆叠布局，用于排列标题、分隔线和聊天列表
                rx.vstack(
                    rx.heading(title, color=rx.color("mauve", 11)),  # 侧边栏标题
                    rx.divider(),  # 分隔线
                    # 遍历状态中的所有聊天标题，为每个创建一个sidebar_chat组件
                    rx.foreach(
                        chat_names, lambda _: chat_menu(_, set_chat_name, del_chat_name)
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
                    InputBarState.set_is_create_chat_modal_open(False),
                ],
                reset_on_submit=True,
            ),
            background_color=rx.color("mauve", 1),  # 使用mauve色系的第1种颜色作为背景
        ),
        open=InputBarState.is_create_chat_modal_open,  # 控制模态框是否打开的状态
        on_open_change=InputBarState.set_is_create_chat_modal_open,  # 模态框打开状态变化时调用的方法
    )


def form_item(item: Parameters) -> rx.Component:
    key = item.mkey
    value = item.mvalue
    mtype = item.mtype
    mselected = item.mselected

    return rx.hstack(
        rx.text(
            key,
            weight="bold",
            justify_content="right",
            font_style="italic",
            color_scheme="pink",
        ),
        rx.match(
            mtype,
            (
                "text",
                rx.input(
                    name=key,
                    flex="1",  # 弹性布局，占满可用空间
                    min_width="10ch",  # 最小宽度为20个字符
                    default_value=value,
                    placeholder=f"请输入{key}",  # 添加占位符提示
                ),
            ),
            (
                "text_area",
                rx.text_area(
                    name=key,
                    flex="1",  # 弹性布局，占满可用空间
                    min_width="10ch",  # 最小宽度为20个字符
                    default_value=value,
                    placeholder=f"请输入{key}",  # 添加占位符提示
                ),
            ),
            (
                "select",
                rx.select(
                    mselected,
                    name=key,
                    default_value=value,
                    required=True,
                ),
            ),
        ),
        spacing="2",  # 子元素间距
        wrap="wrap",  # 超出时自动换行
        width="100%",  # 占满父容器宽度
        align_items="center",
    )


def settings_modal(
    trigger: rx.Component,
    params_fields: list[Parameters],
    set_params_fields: Callable,
) -> rx.Component:
    return rx.dialog.root(  # 对话框根组件
        rx.dialog.trigger(trigger),  # 对话框触发器，传入的参数作为触发元素
        rx.dialog.content(  # 对话框内容区域
            rx.dialog.title(
                rx.hstack(
                    rx.icon("settings", color=rx.color("mauve", 7)),
                    rx.text(
                        "Context Settings",
                        size="4",
                        weight="bold",
                    ),
                    margin_bottom="1em",
                    gap="0.5em",
                ),
            ),
            # 表单内容区域，添加滚动以防内容过多
            rx.box(
                rx.form(
                    rx.foreach(
                        params_fields,
                        lambda item: rx.box(
                            form_item(item),
                            margin_bottom="1em",  # 每个表单项之间增加间距
                        ),
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                color_scheme="gray",
                                variant="soft",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button(
                                "Save",
                                type="submit",
                            ),
                        ),
                        spacing="3",
                        margin_top="32px",
                        justify="end",
                    ),
                    on_submit=[
                        set_params_fields,
                        InputBarState.set_is_settings_modal_open(False),
                    ],
                    reset_on_submit=True,
                    padding="0.5em",
                ),
                max_height="70vh",  # 限制最大高度，防止超出屏幕
                overflow_y="auto",  # 内容过多时可滚动
                padding="0.5em",
            ),
            background_color=rx.color("mauve", 1),  # 使用mauve色系的第1种颜色作为背景
            border_radius="0.5em",  # 圆角边框
            box_shadow="lg",  # 增加阴影提升层次感
            max_width="500px",  # 限制最大宽度，提升可读性
            padding="1.5em",  # 适当增加内边距
            transition="all 0.2s ease-in-out",
        ),
        open=InputBarState.is_settings_modal_open,  # 控制模态框是否打开的状态
        on_open_change=InputBarState.set_is_settings_modal_open,  # 模态框打开状态变化时调用的方法
    )


def inputbar(
    title: str,
    submit_create_chat_instance: Callable,
    chat_names: rx.Var[list[str]],
    set_chat_name: Callable,
    del_chat_instance: Callable,
    submit_input_bar_question: Callable,
    params_fields: list[Parameters],
    submit_input_bar_settings: Callable,
    is_processing: bool,
) -> rx.Component:
    """The action bar to send a new message."""
    return rx.box(
        rx.form(
            rx.vstack(
                rx.text_area(
                    placeholder="发消息...",
                    id="question",
                    flex="1",
                    width="100%",
                    # 核心：取消边框 + 透明背景
                    border="none",  # 移除所有边框
                    background_color="transparent",  # 背景色设为透明（无色）
                    # 可选优化：消除焦点时的默认边框/阴影，避免出现残留样式
                    outline="none",  # 移除获取焦点时的默认外边框
                    box_shadow="none",  # 移除所有阴影（防止有默认阴影）
                    # 可选：调整内边距和行高，让输入更舒适
                    padding="2px 0",  # 仅保留上下内边距，左右无（可按需调整）
                    resize="none",  # 禁止手动调整文本框大小（可选，保持布局统一）
                    color=rx.color("mauve", 12),  # 输入文字颜色（与页面主题匹配）
                    placeholder_color=rx.color(
                        "mauve", 8
                    ),  # 占位符文字颜色（浅一点更美观）
                    min_height="60px",  # 初始最小高度
                    style={  # 核心：通过CSS实现内容自适应高度
                        "overflow-y": "hidden",  # 隐藏垂直滚动条
                        "lineHeight": "1.5",  # 行高，保证文字排版舒适
                    },
                ),
                rx.hstack(
                    # 创建新聊天的模态框，使用消息加号图标作为触发器
                    create_chat_modal(
                        rx.icon_button("message-square-plus"),
                        title,
                        submit_create_chat_instance.stop_propagation(),
                    ),
                    # 侧边栏组件，使用消息图标作为触发器
                    chat_drawer(
                        rx.icon_button(
                            "messages-square", background_color=rx.color("mauve", 6)
                        ),
                        title,
                        chat_names,
                        set_chat_name,
                        del_chat_instance,
                    ),
                    settings_modal(
                        rx.icon_button("settings"),
                        params_fields,
                        submit_input_bar_settings.stop_propagation(),
                    ),
                    rx.button(
                        "Send",
                        loading=is_processing,
                        disabled=is_processing,
                        type="submit",
                    ),
                    # 核心：靠右对齐 + 移除居中margin
                    justify_content="flex-end",  # 子元素整体靠右
                    align_items="center",  # 垂直居中（保留）
                    width="100%",  # 占满父容器宽度（必须，否则靠右无效）
                    gap="8px",  # 图标和按钮之间的间距（可选，更美观）
                    margin_top="5px",
                    spacing="2",
                ),
                width="100%",
                spacing="0",  # 先将默认间距设为0，再用margin微调
                margin="0",  # 消除vstack自身的外边距
                padding="0",  # 消除vstack自身的内边距
            ),
            reset_on_submit=True,
            on_submit=submit_input_bar_question,
            padding_x="6px",  # 保留左右内边距
            padding_y="0",  # 核心：消除form上下内边距
            margin="0",  # 核心：消除form上下外边距
            width="100%",  # form占满父容器宽度，避免留白
        ),
        position="sticky",
        bottom="20px",  # 离底部留间距，强化悬空感（原0改为20px）
        left="0",
        # padding="0",  # 替代原padding_y="16px"和潜在的padding_x，彻底消除内边距
        padding_y="5px",
        backdrop_filter="auto",
        backdrop_blur="lg",
        border_top=f"1px solid {rx.color('mauve', 3)}",
        background_color=rx.color("mauve", 2),
        align="stretch",
        width="100%",
        border_radius="8px",
        border=f"1px solid {rx.color('mauve', 4)}",
        margin_y="16px",
    )
