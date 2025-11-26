# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx
from app.components.common.settings_components import settings_modal
from app.components.novel.prompt_settings import (
    prompt_settings_modal,
)


# 5. 示例：标签内容组件（需根据实际业务实现）--------------------------
def editor_component_form(tab, State) -> rx.Component:
    # 滚动到底部的逻辑
    """小说编辑标签内容（示例实现）"""
    return rx.vstack(
        rx.hstack(
            prompt_settings_modal(rx.icon_button("file-pen-line")),
            rx.text(
                tab.label,
                font_size="1.0em",
                weight="bold",
                justify_content="right",
                font_style="italic",
                color_scheme="pink",
            ),
            margin_bottom="1em",
            align_items="center",
        ),
        # 创建新聊天的模态框，使用消息加号图标作为触发器
        rx.vstack(
            rx.text_area(
                placeholder="(可选项)在这里输入你的要求...",
                value=State.get_input_content,
                on_change=lambda _: State.set_input_content(_),
                width="100%",
                height="4em",
                border_radius="5px",
                border=f"1px solid {rx.color('mauve', 4)}",
                # padding="0.2em",
                font_size="1em",
                resize="vertical",
                id="question",
                style={
                    "overflow-y": "auto",  # 垂直溢出时显示滚动条
                    "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                },
            ),
            rx.hstack(
                # 左侧按钮组（靠左）
                rx.hstack(
                    settings_modal(
                        State,
                        rx.icon_button("settings"),
                    ),
                    rx.button(
                        "生成",
                        loading=State.processing,
                        disabled=State.processing,
                        on_click=State.process_question,
                    ),
                    rx.button(
                        "诊断",
                        loading=State.processing,
                        disabled=State.processing,
                        on_click=State.process_diagnose,  # 诊断逻辑
                        type="button",  # 显式设置为普通按钮
                    ),
                    rx.button(
                        "反馈",
                        loading=State.processing,
                        disabled=State.processing,
                        on_click=State.process_feedback,  # 反馈逻辑
                        type="button",  # 显式设置为普通按钮
                    ),
                    # 让左侧按钮组紧凑排列
                    spacing="1",
                ),
                # 分隔符：自动占据剩余空间，将两侧按钮推开
                rx.spacer(),
                # 右侧按钮（靠右）
                rx.button(
                    "一键式",
                    loading=State.processing,
                    disabled=State.processing,
                    on_click=State.process_one_click,  # 一键式逻辑
                    type="button",  # 显式设置为普通按钮
                ),
                # 确保hstack占满宽度，否则靠右效果不明显
                width="100%",
                # 整体垂直居中对齐
                align_items="center",
                # 可选：调整整体间距
                spacing="1",
            ),
            width="100%",
        ),
        rx.hstack(
            rx.auto_scroll(
                rx.text_area(
                    placeholder="生成过程展示...",
                    value=State.get_output_content,
                    read_only=True,
                    width="100%",
                    height="100%",
                    border_radius="5px",
                    border=f"1px solid {rx.color('mauve', 4)}",
                    padding="1em",
                    font_size="1.05em",
                    resize="vertical",
                ),
                threshold=80,  # 如果用户在 100px 内底部，自动滚动
                padding="0",  # 避免额外内边距
                width="100%",
                height="100%",
                # 优化滚动条样式（可选，提升桌面端体验）
                style={
                    "::-webkit-scrollbar": {
                        "width": "6px",
                        "height": "6px",
                    },
                    "::-webkit-scrollbar-thumb": {
                        "background-color": rx.color("gray", 3),
                        "border-radius": "3px",
                    },
                    "::-webkit-scrollbar-track": {
                        "background-color": rx.color("gray", 1),
                    },
                    "min_height": "300px",
                },
            ),
            rx.vstack(
                rx.text_area(
                    placeholder="生成最终结果展示...",
                    value=State.get_final_content,
                    on_change=State.set_final_content,  # 保存最终结果逻辑
                    width="100%",
                    height="100%",
                    border_radius="5px",
                    border=f"1px solid {rx.color('mauve', 4)}",
                    padding="1em",
                    font_size="1.05em",
                    resize="vertical",
                    id="answer",
                    style={
                        "overflow-y": "auto",  # 垂直溢出时显示滚动条
                        "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                    },
                ),
                rx.hstack(
                    rx.button(
                        "展示",
                        loading=State.saving,
                        disabled=State.saving,
                        on_click=State.final_content_show,  # 展示逻辑
                        bg=rx.color("blue", 4),
                        color="white",
                        _hover={"bg": rx.color("blue", 7)},
                    ),
                    rx.button(
                        "保存",
                        loading=State.saving,  # 建议单独设置保存状态变量，避免与processing冲突
                        disabled=State.saving
                        | ~State.get_final_content,  # 内容为空时禁用
                        on_click=State.final_content_save,  # 展示逻辑,
                        # width="100%",  # 按钮占满宽度，与文本框对齐
                        bg=rx.color("blue", 4),
                        color="white",
                        _hover={"bg": rx.color("blue", 7)},
                    ),
                ),
                width="100%",
                height="100%",
            ),
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        align_items="flex-start",
        gap="1em",
    )
