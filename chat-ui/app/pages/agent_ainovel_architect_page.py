# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx

from app.components import action_bar, chat, navbar, sidebar
from app.states.agent_ainovel_architect_state import AgentAiNovelArchitectState


def agent_ainovel_architect_page() -> rx.Component:
    return rx.hstack(
        sidebar(AgentAiNovelArchitectState),
        rx.vstack(
            navbar(AgentAiNovelArchitectState),
            chat(AgentAiNovelArchitectState),
            action_bar(AgentAiNovelArchitectState),
            background_color=rx.color("mauve", 1),
            color=rx.color("mauve", 12),
            height="100%",
            width="100%",
            align_items="stretch",
            spacing="0",
        ),
        background_color=rx.color("mauve", 1),
        color=rx.color("mauve", 12),
        align_items="stretch",
        spacing="0",
        height="100dvh",
    )
