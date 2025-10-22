# -*- coding: utf-8 -*-
# @Time   : 2025/10/22 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx

from app.components import action_bar, chat, navbar, sidebar
from app.states.agent_ainovel_chapter_state import AgentAiNovelChapterState


def agent_ainovel_chapter_page() -> rx.Component:
    return rx.hstack(
        sidebar(AgentAiNovelChapterState),
        rx.vstack(
            navbar(AgentAiNovelChapterState),
            chat(AgentAiNovelChapterState),
            action_bar(AgentAiNovelChapterState),
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
