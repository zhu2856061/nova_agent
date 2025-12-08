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


class State(rx.State):
    is_settings_modal_open: bool = False

    # 设置参数值的模态框开关
    @rx.event
    def set_is_settings_modal_open(self, is_open: bool):
        self.is_settings_modal_open = is_open


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
            # font_style="italic",
            color=rx.color("mauve", 11),
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
                    weight="bold",
                    justify_content="right",
                    color=rx.color("mauve", 11),
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
                    color=rx.color("mauve", 11),
                ),
            ),
            (
                "select",
                rx.select(
                    mselected,
                    name=key,
                    default_value=value,
                    required=True,
                    color=rx.color("mauve", 11),
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
                        size="2",
                        weight="bold",
                        color=rx.color("mauve", 11),
                    ),
                    align_items="center",  # 垂直居中（保留）
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
                        State.set_is_settings_modal_open(False),
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
        open=State.is_settings_modal_open,  # 控制模态框是否打开的状态
        on_open_change=State.set_is_settings_modal_open,  # 模态框打开状态变化时调用的方法
    )
