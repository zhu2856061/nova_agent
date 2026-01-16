import reflex as rx
from app.states.chat_state import ChatState


def input_section() -> rx.Component:
    return rx.el.form(
        rx.el.div(
            rx.el.textarea(
                name="prompt_input",
                placeholder="How can I help you today?",
                class_name="w-full bg-transparent text-neutral-300 placeholder-neutral-500 focus:outline-none resize-none text-lg p-4 min-h-[80px]",
                rows=3,
                enter_key_submit=True,
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.button(
                        rx.icon(
                            "plus",
                            size=20,
                            class_name="text-neutral-400",
                        ),
                        type="button",
                        class_name="p-2 bg-[#40414F] hover:bg-[#50515f] rounded-md",
                    ),
                    rx.el.button(
                        rx.icon(
                            "paperclip",
                            size=20,
                            class_name="text-neutral-400",
                        ),
                        type="button",
                        class_name="p-2 bg-[#40414F] hover:bg-[#50515f] rounded-md",
                    ),
                    class_name="flex items-center space-x-2",
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon(
                            "arrow-up",
                            size=20,
                            class_name="text-white",
                        ),
                        type="submit",
                        class_name="p-2 bg-[#E97055] hover:bg-[#d3654c] rounded-md aspect-square",
                        is_disabled=ChatState.is_streaming,
                    ),
                    class_name="flex items-center",
                ),
                class_name="flex items-center justify-between p-2 pt-0",
            ),
            class_name="bg-[#353740] rounded-xl shadow-lg w-full flex flex-col",
        ),
        on_submit=ChatState.send_initial_message_and_navigate,
        reset_on_submit=True,
        class_name="w-full",
    )
