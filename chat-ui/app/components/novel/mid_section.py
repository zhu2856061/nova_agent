# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx
from reflex.constants.colors import ColorType

from app.states.state import Message


def message_content(text: str, color: ColorType) -> rx.Component:
    """Create a message content component.

    Args:
        text: The text to display.
        color: The color of the message.

    Returns:
        A component displaying the message.
    """
    return rx.markdown(
        text,
        background_color=rx.color(color, 4),
        color=rx.color(color, 12),
        display="inline-block",
        padding_inline="1em",
        border_radius="8px",
        style={
            "pre": {
                "overflow-x": "auto",  # 横向滚动条
                "white-space": "pre",  # 不自动换行
                "width": "48em",  # 限制最大宽度
            }
        },
    )


def message(message: Message) -> rx.Component:
    return rx.box(
        rx.cond(
            # 条件：判断消息角色是否为用户
            message.role == "user",
            # 条件为真时渲染（用户消息）
            rx.box(
                message_content(message.content, "mauve"),
                text_align="right",
                margin_bottom="8px",
            ),
            # 条件为假时渲染（其他角色消息，如系统/AI）
            rx.box(
                message_content(message.content, "accent"),
                text_align="left",
                margin_bottom="8px",
            ),
        ),
        max_width="50em",
        margin_inline="auto",
    )


def chat(AgentState) -> rx.Component:
    """List all the messages in a single conversation."""
    return rx.auto_scroll(
        rx.foreach(AgentState.show_chat_content, message),
        flex="1",
        padding="8px",
    )
