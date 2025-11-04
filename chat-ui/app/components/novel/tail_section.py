# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import reflex as rx


def novel_footer(State) -> rx.Component:
    """The action bar to send a new message."""
    return rx.center(
        rx.vstack(
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
