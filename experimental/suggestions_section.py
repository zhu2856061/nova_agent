import reflex as rx

from app.states.chat_state import ChatState


def suggestion_chip(icon_name: str, text: str) -> rx.Component:
    return rx.el.button(
        rx.icon(
            icon_name,
            size=18,
            class_name="mr-2 text-neutral-300",
        ),
        rx.el.span(text, class_name="text-sm text-neutral-200"),
        on_click=lambda: ChatState.submit_suggestion_as_prompt(text),
        type="button",
        class_name="bg-[#2A2B2E] px-4 py-2 rounded-lg flex items-center hover:bg-[#3a3b3e] transition-colors",
    )


def suggestions_section() -> rx.Component:
    return rx.el.div(
        suggestion_chip("disc_3", "Write"),
        suggestion_chip("graduation-cap", "Learn"),
        suggestion_chip("file_code_2", "Code"),
        suggestion_chip("coffee", "Life stuff"),
        suggestion_chip("lightbulb", "Claude's choice"),
        class_name="flex flex-wrap items-center justify-center gap-3",
    )
