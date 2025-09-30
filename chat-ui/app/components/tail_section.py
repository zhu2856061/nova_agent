# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import reflex as rx


def form_item(item: dict) -> rx.Component:
    key = item["mkey"]
    value = item["mvalue"]
    mtype = item.get("mtype", "text")
    mselected = item.get("mselected")

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
                "select",
                rx.select(
                    mselected,
                    name=key,
                    default_value=value,
                    required=True,
                ),
            ),
        ),
        # rx.input(
        #     name=key,
        #     flex="1",  # 弹性布局，占满可用空间
        #     min_width="10ch",  # 最小宽度为20个字符
        #     default_value=value,
        #     placeholder=f"请输入{key}",  # 添加占位符提示
        # ),
        spacing="2",  # 子元素间距
        wrap="wrap",  # 超出时自动换行
        width="100%",  # 占满父容器宽度
        align_items="center",
    )


def settings_modal(State, trigger) -> rx.Component:
    """用于创建新聊天的模态框组件"""
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
            rx.dialog.description(
                "change settings in the session",
                size="1",
                margin_bottom="8px",
            ),
            # 表单内容区域，添加滚动以防内容过多
            rx.box(
                rx.form(
                    rx.foreach(
                        State.params_fields,
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
                    on_submit=State.update_params_fields,  # 表单提交时调用创建聊天的方法
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
        open=State.is_params_settings_modal_open,  # 控制模态框是否打开的状态
        on_open_change=State.set_is_params_settings_modal_open,  # 模态框打开状态变化时调用的方法
    )


def action_bar(State) -> rx.Component:
    """The action bar to send a new message."""
    return rx.center(
        rx.vstack(
            rx.form(
                rx.hstack(
                    # 创建新聊天的模态框，使用消息加号图标作为触发器
                    settings_modal(
                        State,
                        rx.icon_button("settings"),
                    ),
                    rx.input(
                        rx.input.slot(
                            rx.tooltip(
                                rx.icon("info", size=18),
                                content="Enter a question to get a response.",
                            )
                        ),
                        placeholder="Input something...",
                        id="question",
                        flex="1",
                    ),
                    rx.button(
                        "Send",
                        loading=State.processing,
                        disabled=State.processing,
                        type="submit",
                    ),
                    max_width="50em",
                    margin="0 auto",
                    align_items="center",
                ),
                reset_on_submit=True,
                on_submit=State.process_question,
            ),
            rx.text(
                "Nova AI integrates cutting-edge model technology, making efficient work accessible.",
                text_align="center",
                font_size=".7em",
                color=rx.color("mauve", 10),
            ),
            width="100%",
            padding_x="16px",
            align="stretch",
        ),
        position="sticky",
        bottom="0",
        left="0",
        padding_y="16px",
        backdrop_filter="auto",
        backdrop_blur="lg",
        border_top=f"1px solid {rx.color('mauve', 3)}",
        background_color=rx.color("mauve", 2),
        align="stretch",
        width="100%",
    )
