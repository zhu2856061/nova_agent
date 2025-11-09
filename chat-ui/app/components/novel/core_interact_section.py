# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import reflex as rx
from app.components.chat.tail_section import settings_modal
from app.states.interact_ainovel_state import NovelStepMenu


# 1. 提取样式常量（统一维护）--------------------------
class NovelWorkspaceStyle:
    """小说工作区标签页样式常量"""

    # 尺寸相关
    TABS_ROOT_WIDTH = "100%"  # 标签页根容器宽度
    TABS_LIST_WIDTH = "12em"  # 垂直布局时标签列表宽度
    TABS_LIST_HEIGHT = "100%"  # 垂直布局时标签列表高度
    TABS_CONTENT_PADDING = "1.5em"  # 内容区内边距
    TRIGGER_HEIGHT = "3.2em"  # 标签触发按钮高度
    TRIGGER_FONT_SIZE = "1.0em"  # 标签文字大小

    # 颜色相关
    TABS_LIST_BG = rx.color("mauve", 2)  # 标签列表背景色
    TRIGGER_HOVER_BG = rx.color("mauve", 5)  # 标签悬浮背景色
    TRIGGER_ACTIVE_BG = rx.color("mauve", 5)  # 标签选中背景色
    TEXT_COLOR = rx.color("mauve", 12)  # 文字颜色
    BORDER_COLOR = rx.color("mauve", 4)  # 边框颜色
    # 样式相关
    BORDER_RADIUS = "5px"  # 全局圆角
    TRIGGER_BORDER_RADIUS = "5px"  # 标签按钮圆角
    BOX_SHADOW = "0 2px 10px rgba(0,0,0,0.05)"  # 轻微阴影（提升层次感）
    TRANSITION_DURATION = "0.2s"  # 过渡动画时长


# 5. 示例：标签内容组件（需根据实际业务实现）--------------------------
def editor_component_form(tab: NovelStepMenu, State) -> rx.Component:
    """小说编辑标签内容（示例实现）"""
    return rx.vstack(
        rx.text(tab.label, font_size="0.8em", weight="bold", margin_bottom="1em"),
        # 创建新聊天的模态框，使用消息加号图标作为触发器
        rx.form(
            rx.vstack(
                rx.text_area(
                    placeholder="在这里输入你的要求...",
                    value=State.get_input_content,
                    on_change=State.set_input_content,
                    width="100%",
                    height="5em",
                    border_radius="5px",
                    border=f"1px solid {NovelWorkspaceStyle.BORDER_COLOR}",
                    padding="1em",
                    font_size="1.05em",
                    resize="vertical",
                    id="question",
                    style={
                        "overflow-y": "auto",  # 垂直溢出时显示滚动条
                        "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                    },
                ),
                rx.hstack(
                    # 左侧按钮组（靠左）
                    rx.hstack(
                        settings_modal(
                            State,
                            rx.icon_button("settings"),
                        ),
                        rx.button(
                            "生成",
                            loading=State.processing,
                            disabled=State.processing,
                            type="submit",
                        ),
                        rx.button(
                            "诊断",
                            loading=State.processing,
                            disabled=State.processing,
                            on_click=State.process_diagnose,  # 诊断逻辑
                            type="button",  # 显式设置为普通按钮
                        ),
                        rx.button(
                            "反馈",
                            loading=State.processing,
                            disabled=State.processing,
                            on_click=State.process_feedback,  # 反馈逻辑
                            type="button",  # 显式设置为普通按钮
                        ),
                        # 让左侧按钮组紧凑排列
                        spacing="1",
                    ),
                    # 分隔符：自动占据剩余空间，将两侧按钮推开
                    rx.spacer(),
                    # 右侧按钮（靠右）
                    rx.button(
                        "一键式",
                        loading=State.processing,
                        disabled=State.processing,
                        on_click=State.process_one_click,  # 一键式逻辑
                        type="button",  # 显式设置为普通按钮
                    ),
                    # 确保hstack占满宽度，否则靠右效果不明显
                    width="100%",
                    # 整体垂直居中对齐
                    align_items="center",
                    # 可选：调整整体间距
                    spacing="1",
                ),
            ),
            reset_on_submit=True,
            on_submit=State.process_question,
        ),
        rx.hstack(
            rx.text_area(
                placeholder="生成过程展示...",
                value=State.get_output_content,
                width="100%",
                height="100%",
                border_radius="5px",
                border=f"1px solid {NovelWorkspaceStyle.BORDER_COLOR}",
                padding="1em",
                font_size="1.05em",
                resize="vertical",
                id="process_answer",
                style={
                    "overflow-y": "auto",  # 垂直溢出时显示滚动条
                    "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                },
            ),
            rx.form(
                rx.vstack(
                    rx.text_area(
                        placeholder="生成最终结果展示...",
                        value=State.get_final_content,
                        on_change=State.set_final_content,  # 保存最终结果逻辑
                        width="100%",
                        height="100%",
                        border_radius="5px",
                        border=f"1px solid {NovelWorkspaceStyle.BORDER_COLOR}",
                        padding="1em",
                        font_size="1.05em",
                        resize="vertical",
                        id="answer",
                        style={
                            "overflow-y": "auto",  # 垂直溢出时显示滚动条
                            "overflow-x": "hidden",  # 禁止水平滚动（避免文本过长导致横向滚动）
                        },
                    ),
                    rx.button(
                        "保存",
                        loading=State.saving,  # 建议单独设置保存状态变量，避免与processing冲突
                        disabled=State.saving
                        | ~State.get_final_content,  # 内容为空时禁用
                        type="submit",
                        width="100%",  # 按钮占满宽度，与文本框对齐
                        bg=rx.color("blue", 4),
                        color="white",
                        _hover={"bg": rx.color("blue", 7)},
                    ),
                    width="100%",
                    height="100%",
                ),
                reset_on_submit=True,
                on_submit=State.save_final_content,
                width="100%",
                height="100%",
            ),
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        align_items="flex-start",
        gap="1em",
    )


def settings_component(tab: NovelStepMenu, state) -> rx.Component:
    """设置标签内容（示例实现）"""
    return rx.vstack(
        rx.text("工作区设置", font_size="1.5em", weight="bold", margin_bottom="1.5em"),
        rx.box(
            rx.text("主题颜色："),
            rx.select(
                ["默认（Mauve）", "蓝色（Blue）", "绿色（Green）", "深色（Dark）"],
                value="蓝色（Blue）",
                width="20em",
                margin_top="0.5em",
            ),
            margin_bottom="1.5em",
        ),
        width="100%",
        height="100%",
        align_items="flex-start",
        gap="1em",
    )
