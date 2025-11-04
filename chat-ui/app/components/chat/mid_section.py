# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx
from app.states.state import Message
from reflex.constants.colors import ColorType


# -------------------------- 1. 提取常量（统一维护，便于修改）--------------------------
class ChatStyle:
    """聊天组件样式常量"""

    # 间距相关
    MESSAGE_MARGIN_BOTTOM = "0.5rem"  # 消息底部间距（用rem更适配字体大小）
    MESSAGE_PADDING_INLINE = "1.1rem"  # 消息左右内边距
    MESSAGE_PADDING_BLOCK = "0.5rem"  # 消息上下内边距
    ICON_MESSAGE_GAP = "0.5rem"  # 机器人图标与消息的间距
    CHAT_PADDING = "1rem"  # 聊天区内边距

    # 尺寸相关
    MAX_MESSAGE_WIDTH_DESKTOP = "80%"  # 桌面端消息最大宽度（占父容器80%，更响应式）
    MAX_MESSAGE_WIDTH_MOBILE = "90%"  # 移动端消息最大宽度
    CODE_BLOCK_MAX_WIDTH = "100%"  # 代码块最大宽度（适应消息宽度）
    ICON_CONTAINER_SIZE = "2rem"  # 图标容器固定尺寸（适配16px图标，留足边距）
    ICON_FIXED_SIZE = 24  # 图标固定大小（不再随父容器变化）

    # 颜色相关
    USER_MESSAGE_COLOR = "mauve"  # 用户消息色系
    AI_MESSAGE_COLOR = "accent"  # AI消息色系
    CODE_BLOCK_BG = rx.color("gray", 2)  # 代码块背景色（独立设置，更醒目）


# -------------------------- 2. 优化消息内容组件 --------------------------
def message_content(text, color: ColorType) -> rx.Component:
    """
    渲染消息内容气泡（支持Markdown，优化代码块样式）
    :param text: 消息文本（支持None，避免空值报错）
    :param color: 气泡色系
    """
    # 容错处理：空消息显示占位符
    # safe_text = text.strip() if text and text.strip() else "（无内容）"

    return rx.markdown(
        text.strip() | "（无内容）",
        # 优化内边距：上下+左右都设置，气泡更饱满
        padding=f"{ChatStyle.MESSAGE_PADDING_BLOCK} {ChatStyle.MESSAGE_PADDING_INLINE}",
        background_color=rx.color(color, 4),
        color=rx.color(color, 12),
        display="inline-block",
        border_radius="12px",  # 更大圆角，更现代
        line_height="1.6",  # 行高优化，提升可读性
        # 优化代码块样式
        style={
            "pre": {
                "overflow-x": "auto",
                "white-space": "pre",
                "width": ChatStyle.CODE_BLOCK_MAX_WIDTH,
                "background-color": ChatStyle.CODE_BLOCK_BG,  # 代码块独立背景
                "padding": "0.75rem",  # 代码块内边距
                "border-radius": "8px",  # 代码块圆角
                "font-size": "0.9rem",  # 代码字体大小
            },
            # 优化链接样式
            "a": {
                "color": rx.color(color, 10),
                "text-decoration": "underline",
                "text-underline-offset": "2px",
            },
        },
    )


# -------------------------- 3. 优化单条消息组件 --------------------------
def message(message: Message) -> rx.Component:
    return rx.cond(
        message.role == "user",
        # 关键修改1：用户消息改为「消息内容 + 图标」的水平布局（右对齐）
        rx.box(
            rx.hstack(
                message_content(message.content, ChatStyle.USER_MESSAGE_COLOR),
                rx.box(
                    rx.icon(
                        "user-round",
                        size=ChatStyle.ICON_FIXED_SIZE,
                        color=rx.color(ChatStyle.USER_MESSAGE_COLOR, 8),
                    ),
                    width=ChatStyle.ICON_CONTAINER_SIZE,
                    height=ChatStyle.ICON_CONTAINER_SIZE,
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    flex_shrink="0",
                ),
                gap=ChatStyle.ICON_MESSAGE_GAP,
                align_items="flex-start",
                # 关键修改1：flex容器内部子组件右对齐（核心修复）
                justify_content="flex-end",
                # 关键修改2：让hstack占满父容器宽度（确保justify_content生效）
                width="100%",
            ),
            text_align="right",  # 整体右对齐（确保布局在右侧）
            margin_bottom=ChatStyle.MESSAGE_MARGIN_BOTTOM,
            max_width=[
                ChatStyle.MAX_MESSAGE_WIDTH_MOBILE,
                ChatStyle.MAX_MESSAGE_WIDTH_DESKTOP,
            ],
            margin_inline="auto",
        ),
        # AI消息部分（无修改，保持原有风格）
        rx.box(
            rx.hstack(
                rx.box(
                    rx.icon(
                        "bot-message-square",
                        size=ChatStyle.ICON_FIXED_SIZE,
                        color=rx.color(ChatStyle.AI_MESSAGE_COLOR, 8),
                    ),
                    width=ChatStyle.ICON_CONTAINER_SIZE,
                    height=ChatStyle.ICON_CONTAINER_SIZE,
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    flex_shrink="0",
                ),
                message_content(message.content, ChatStyle.AI_MESSAGE_COLOR),
                gap=ChatStyle.ICON_MESSAGE_GAP,
                align_items="flex-start",
            ),
            text_align="left",
            margin_bottom=ChatStyle.MESSAGE_MARGIN_BOTTOM,
            max_width=[
                ChatStyle.MAX_MESSAGE_WIDTH_MOBILE,
                ChatStyle.MAX_MESSAGE_WIDTH_DESKTOP,
            ],
            margin_inline="auto",
        ),
    )


# -------------------------- 4. 优化聊天列表组件 --------------------------
def chat(agent_state: type) -> rx.Component:
    """
    聊天历史列表（自动滚动到最新消息，优化布局适配）
    :param agent_state: 状态类（类型注解更精确）
    """
    return rx.auto_scroll(
        # 容错处理：消息列表为空时显示提示
        rx.foreach(agent_state.show_chat_content, message),
        flex="1",  # 占满父容器剩余高度
        padding=ChatStyle.CHAT_PADDING,
        background_color=rx.color("gray", 1),  # 聊天区背景色（轻微灰色，区分其他区域）
        border_radius="8px",  # 聊天区整体圆角
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
        },
    )
