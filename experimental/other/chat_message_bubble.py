import reflex as rx

from app.states.chat_state import Message


def user_message_bubble(
    message_content: str,
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    message_content,
                    class_name="text-neutral-200 whitespace-pre-wrap break-words leading-relaxed",
                ),
                class_name="bg-[#353740] p-3 rounded-lg shadow",
            ),
            rx.el.div(
                "NR",
                class_name="flex items-center justify-center w-8 h-8 bg-neutral-700 text-neutral-300 rounded-full text-sm font-medium ml-4 shrink-0",
            ),
            class_name="flex items-start flex-row-reverse",
        ),
        class_name="w-full flex justify-end mb-6",
    )


def ai_message_bubble(message: Message) -> rx.Component:
    is_initial = message.is_initial_greeting
    return rx.el.div(
        rx.el.div(
            rx.cond(
                is_initial,
                rx.el.div(
                    "NR",
                    class_name="flex items-center justify-center w-8 h-8 bg-neutral-600 text-neutral-200 rounded-full text-sm font-medium mr-3 shrink-0",
                ),
                rx.icon(
                    "sparkle",
                    class_name="text-[#E97055] w-8 h-8 mr-3 shrink-0 p-1",
                ),
            ),
            rx.el.div(
                rx.el.p(
                    message.content,
                    class_name=rx.cond(
                        is_initial,
                        "font-medium text-neutral-100 whitespace-pre-wrap break-words leading-relaxed",
                        "text-neutral-200 whitespace-pre-wrap break-words leading-relaxed",
                    ),
                ),
                rx.cond(
                    is_initial == False,
                    rx.el.div(
                        rx.el.div(
                            rx.icon(
                                "copy",
                                size=18,
                                class_name="text-neutral-400 hover:text-neutral-200 cursor-pointer",
                            ),
                            rx.icon(
                                "thumbs-up",
                                size=18,
                                class_name="text-neutral-400 hover:text-neutral-200 cursor-pointer",
                            ),
                            rx.icon(
                                "thumbs-down",
                                size=18,
                                class_name="text-neutral-400 hover:text-neutral-200 cursor-pointer",
                            ),
                            rx.el.button(
                                "Retry",
                                rx.icon(
                                    "chevron-down",
                                    size=16,
                                    class_name="ml-1",
                                ),
                                type="button",
                                class_name="flex items-center text-neutral-400 hover:text-neutral-200 bg-transparent p-0 text-sm font-medium",
                            ),
                            class_name="flex items-center space-x-3",
                        ),
                        rx.el.p(
                            "Claude can make mistakes. Please double-check responses.",
                            class_name="text-xs text-neutral-500",
                        ),
                        class_name="flex items-center justify-between mt-3 w-full",
                    ),
                    rx.el.div(),
                ),
                class_name="bg-[#2A2B2E] p-3 rounded-lg shadow flex-grow",
            ),
            class_name="flex items-start",
        ),
        class_name="w-full mb-6",
    )


def chat_message_bubble_component(message: Message, index: int) -> rx.Component:
    return rx.cond(
        message.role == "user",
        user_message_bubble(message.content),
        ai_message_bubble(message),
    )
