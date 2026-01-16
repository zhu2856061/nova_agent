import reflex as rx


def greeting_section() -> rx.Component:
    return rx.el.div(
        rx.icon(
            "sparkle",
            class_name="text-[#E97055] mr-3",
            size=36,
        ),
        rx.el.h1(
            "Good afternoon!",
            class_name="text-4xl font-['Lora'] text-neutral-100",
        ),
        class_name="flex items-center justify-center",
    )
