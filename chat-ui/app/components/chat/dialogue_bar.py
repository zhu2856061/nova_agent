# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import reflex as rx
from reflex.constants.colors import ColorType


class Message(rx.Model):
    role: str = "assistant"
    content: str = ""


# -------------------------- 2. 优化消息内容组件 --------------------------
def message_content(text, color: ColorType) -> rx.Component:
    """
    渲染消息内容气泡（支持Markdown，优化代码块样式）
    :param text: 消息文本（支持None，避免空值报错）
    :param color: 气泡色系
    """
    return rx.markdown(
        text.strip() | "（无内容）",
        # 气泡内边距：上下0.5rem，左右0.8rem，保证文字与气泡边框的间距
        padding="0.1rem 0.8rem",
        # 气泡背景色：基于传入的主题色系，取3号浅色色阶（柔和背景）
        background_color=rx.color(color, 3),
        # 气泡文字色：基于传入的主题色系，取12号深色色阶（高对比度，提升可读性）
        color=rx.color(color, 12),
        # 显示模式：inline-block让气泡宽度随内容自适应（核心，避免占满整行）
        display="inline-block",
        # 气泡圆角：8px大圆角，符合现代聊天框设计风格
        border_radius="8px",
        # 行高：优化文字排版，避免行间距过密
        line_height="1.2",  # 行高优化，提升可读性
        # 最大宽度限制，避免超长文本/代码块撑破气泡
        max_width="80%",
        # 超长文本自动换行（针对无空格的长字符串）
        word_break="break-word",
        # 优化代码块样式
        style={
            "pre": {
                "overflow-x": "auto",
                "white-space": "pre",
                "width": "100%",
                "background-color": rx.color("gray", 2),  # 代码块独立背景
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
    """
    根据消息角色（用户/AI）渲染不同样式的聊天消息组件
    :param message: 单个消息对象，包含role（角色）和content（内容）属性
    :return: 条件渲染后的聊天消息组件
    """
    return rx.cond(
        message.role == "user",
        # 分支1：用户消息渲染逻辑（右对齐，紫色系，带用户图标）
        rx.box(
            # 水平堆叠容器：包含「消息内容气泡」和「用户图标」
            rx.hstack(
                # 渲染用户消息内容气泡，使用"mauve"（淡紫色）色系
                message_content(message.content, "mauve"),
                # 用户图标容器：固定尺寸的圆形/方形图标框
                rx.box(
                    # 渲染用户图标：user-round（圆形用户图标），尺寸24px
                    rx.icon("user-round", size=24, color=rx.color("mauve", 8)),
                    width="2rem",  # 图标容器宽度：2rem（约32px）
                    height="2rem",  # 图标容器高度：2rem（约32px）
                    display="flex",  # 开启flex布局，用于图标居中
                    align_items="center",  # 垂直居中图标
                    justify_content="center",  # 水平居中图标
                    flex_shrink="0",  # 关键：图标容器不被挤压，保持固定尺寸
                ),
                gap="0.5rem",  # 消息气泡与图标之间的间距
                align_items="flex-start",  # 子组件顶部对齐（气泡和图标顶部平齐）
                justify_content="flex-end",  # 核心：hstack内部子组件整体右对齐
                width="100%",  # 关键：hstack占满父容器宽度，确保右对齐生效
            ),
            text_align="left",  # 整体容器文本左对齐，兜底布局
            margin_bottom="0.8rem",  # 消息之间的底部间距
            max_width="95%",  # 响应式最大宽度
            margin_inline="auto",  # 水平方向自动边距，让容器在父级中居中
        ),
        # 分支2：AI消息渲染逻辑（左对齐，强调色系，带机器人图标）
        rx.box(
            # 水平堆叠容器：包含「机器人图标」和「AI消息内容气泡」
            rx.hstack(
                # AI图标容器：固定尺寸的图标框
                rx.box(
                    # 渲染机器人图标：bot-message-square（方形机器人消息图标）
                    rx.icon("bot-message-square", size=24, color=rx.color("accent", 8)),
                    width="2rem",  # 图标容器宽度
                    height="2rem",  # 图标容器高度
                    display="flex",  # 开启flex布局居中图标
                    align_items="center",  # 垂直居中图标
                    justify_content="center",  # 水平居中图标
                    flex_shrink="0",  # 图标容器不被挤压，保持固定尺寸
                ),
                # 渲染AI消息内容气泡，使用"accent"（项目强调色）色系
                message_content(message.content, "accent"),
                gap="0.5rem",  # 图标与消息气泡之间的间距
                align_items="flex-start",  # 子组件顶部对齐
            ),
            text_align="left",  # 整体容器文本左对齐
            margin_bottom="0.8rem",  # 消息之间的底部间距
            max_width="95%",  # 响应式最大宽度
            margin_inline="auto",  # 水平方向自动边距，让容器在父级中居中
        ),
    )


# -------------------------- 4. 优化聊天列表组件 --------------------------
def dialoguebar(messages) -> rx.Component:
    """
    聊天历史列表（自动滚动到最新消息，优化布局适配）
    :param agent_state: 状态类（类型注解更精确）
    """
    return rx.auto_scroll(
        # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
        # 这一行是触发同步的“钩子”
        # rx.box(
        #     on_mount=DialogueState.init_dialogue,  # 页面加载时执行一次
        #     display="none",  # 完全隐藏，不影响布局
        # ),
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # 容错处理：消息列表为空时显示提示
        rx.foreach(messages, message),
        flex="1",  # 占满父容器剩余高度
        padding="1rem",
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
