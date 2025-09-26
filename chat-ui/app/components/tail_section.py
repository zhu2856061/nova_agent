# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx


def action_bar(State) -> rx.Component:
    """The action bar to send a new message."""
    return rx.center(
        rx.vstack(
            rx.form(
                rx.hstack(
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
