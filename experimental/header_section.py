import reflex as rx


def header_section() -> rx.Component:
    return rx.el.div(
        rx.el.p(
            "Free plan",
            rx.el.span(" . ", class_name="mx-1"),
            rx.el.a(
                "Upgrade",
                href="#",
                class_name="text-blue-400 hover:underline",
            ),
            class_name="text-sm text-neutral-400",
        ),
        class_name="bg-[#2A2B2E] px-4 py-2 rounded-lg shadow",
    )
