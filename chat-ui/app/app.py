# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx

from app.pages.agent_memorizer_page import memorizer_page
from app.pages.chat_page import chat_page


def redirect_component():
    # 根路径组件，仅用于重定向
    return rx.box(
        rx.vstack(
            # 替代的加载动画 - 使用旋转的方形
            rx.box(
                width="60px",
                height="60px",
                border="4px solid #e2e8f0",
                border_top="4px solid #3b82f6",
                border_radius="50%",
                animation="spin 1s linear infinite",
            ),
            # 跳转文本，添加淡入效果
            rx.text(
                "正在跳转至聊天页面...",
                size="4",
                weight="medium",
                color_scheme="crimson",
                high_contrast=True,
            ),
            spacing="8",
            align="center",
            # 占据整个屏幕
            height="100vh",
            background_color=rx.color("mauve", 3),
        ),
        on_mount=lambda: rx.redirect("/chat/llm"),
    )


# Add state and page to the app.
app = rx.App(theme=rx.theme(appearance="dark", accent_color="green"))

app.add_page(
    component=redirect_component,
    title="Nova AI",
    route="/",  # 根路径
    image="novaait.png",
)

# chat模式
app.add_page(
    component=chat_page,
    title="Nova chat",
    route="/chat/llm",
    image="novaait.png",
)

# agent 模式
app.add_page(
    component=memorizer_page,
    title="Nova Agent",
    route="/agent/memorizer",
    image="novaait.png",
)
# app.add_page(
#     component=agent_researcher_page,
#     title="Nova Agent",
#     route="/agent/researcher",
#     image="novaait.png",
# )
# app.add_page(
#     component=agent_wechat_researcher_page,
#     title="Nova Agent",
#     route="/agent/wechat_researcher",
#     image="novaait.png",
# )
# app.add_page(
#     component=agent_ainovel_architect_page,
#     title="Nova Agent",
#     route="/agent/ainovel_architect",
#     image="novaait.png",
# )
# app.add_page(
#     component=agent_ainovel_chapter_page,
#     title="Nova Agent",
#     route="/agent/ainovel_chapter",
#     image="novaait.png",
# )

# app.add_page(
#     component=interact_ainovel_architect_page,
#     title="Nova Interact",
#     route="/interact/ainovel",
#     image="novaait.png",
# )

# # task 模式
# app.add_page(
#     component=task_deepresearcher_page,
#     title="Nova Task",
#     route="/task/deepresearcher",
#     image="novaait.png",
# )
# app.add_page(
#     component=task_ainovel_page,
#     title="Nova Task",
#     route="/task/ainovel",
#     image="novaait.png",
# )
