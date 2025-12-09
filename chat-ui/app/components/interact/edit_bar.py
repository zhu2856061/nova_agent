# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from typing import Callable

import reflex as rx
from app.components.common.context_settings import (
    Parameters,
    settings_modal,
)
from app.components.interact.prompt_settings import (
    prompt_settings_modal,
)


def editor_prompt_bar(
    label,
    is_saving,
    get_workspace_final_content,
    save_workspace_all_content,
):
    return rx.hstack(
        # 左侧区域：编辑图标弹窗 + 标签文本
        rx.hstack(
            prompt_settings_modal(
                rx.icon_button(
                    rx.icon("file-pen-line", size=18),
                    size="1",
                    border_radius="lg",  # 关键：圆角
                    padding="0.35rem",
                    background_color=rx.color("mauve", 5),
                    color=rx.color("mauve", 11),
                    variant="soft",
                    cursor="pointer",
                    _hover={
                        "background_color": rx.color("mauve", 7),
                        "transform": "scale(1.05)",
                    },
                ),
            ),
            rx.text(
                label,
                font_size="0.8em",
                font_weight="bold",  # 规范属性名（weight → font_weight）
                color_scheme="pink",
                flex="1",  # 占满剩余空间，推动右侧按钮靠右
            ),
            align_items="center",
            flex="1",  # 确保左侧区域占据主要宽度
        ),
        # 右侧区域：展示 + 保存按钮（固定靠右）
        rx.button(
            "Save",
            loading=is_saving,
            disabled=is_saving | ~get_workspace_final_content,
            on_click=save_workspace_all_content,
            bg=rx.color("blue", 4),
            size="1",
            color="white",
            _hover={"bg": rx.color("blue", 7)},
        ),
        align_items="center",  # 外层垂直居中（核心）
        justify_content="space-between",
        width="100%",
        # min_height="40px",  # 可选：固定最小高度，确保垂直居中更稳定
        # padding_y="0.5em",  # 可选：上下内边距，优化视觉居中感
    )


def editor_input_bar(
    input_text,
    set_input_text: Callable,
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
                    value=input_text,  # 绑定 State
                    on_change=set_input_text,  # 更新 State
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
                    settings_modal(
                        rx.icon_button(
                            rx.icon("settings", size=14),
                            size="1",
                            border_radius="lg",  # 关键：圆角
                            padding="0.35rem",
                            background_color=rx.color("mauve", 5),
                            color=rx.color("mauve", 11),
                            variant="soft",
                            cursor="pointer",
                            _hover={
                                "background_color": rx.color("mauve", 7),
                                "transform": "scale(1.05)",
                            },
                        ),
                        params_fields,
                        submit_input_bar_settings.stop_propagation(),
                    ),
                    rx.button(
                        "Send",
                        loading=is_processing,
                        disabled=is_processing,
                        size="1",
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
        # margin_y="16px",
    )


def editor_show_bar(
    get_workspace_output_content,
    get_workspace_final_content,
    set_workspace_final_content,
):
    return rx.hstack(
        rx.auto_scroll(
            rx.text_area(
                placeholder="生成过程展示...",
                value=get_workspace_output_content,
                read_only=True,
                width="100%",
                height="100%",
                border_radius="5px",
                border=f"1px solid {rx.color('mauve', 4)}",
                padding="1em",
                font_size="1.05em",
            ),
            width="100%",
            height="100%",
            # 优化滚动条样式（可选，提升桌面端体验）
            style={
                # Firefox
                "scrollbar-width": "thin",
                "scrollbar-color": f"{rx.color('mauve', 7)} transparent",
                # WebKit (Chrome, Safari, Edge)
                "&::-webkit-scrollbar": {
                    "width": "6px",
                },
                "&::-webkit-scrollbar-track": {
                    "background": "transparent",
                    "border-radius": "3px",
                },
                "&::-webkit-scrollbar-thumb": {
                    "background": rx.color("mauve", 7),
                    "border-radius": "3px",
                },
                "&::-webkit-scrollbar-thumb:hover": {
                    "background": rx.color("mauve", 9),
                },
            },
        ),
        rx.vstack(
            rx.text_area(
                placeholder="生成最终结果展示...",
                value=get_workspace_final_content,
                on_change=set_workspace_final_content,
                width="100%",
                height="100%",
                border_radius="5px",
                border=f"1px solid {rx.color('mauve', 4)}",
                padding="1em",
                font_size="1.05em",
                id="answer",
                style={
                    "overflow-y": "auto",  # 垂直溢出时显示滚动条
                    "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                },
            ),
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
    )
