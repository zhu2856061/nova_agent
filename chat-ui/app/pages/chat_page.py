# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import uuid
from typing import Any

import reflex as rx

from app.api.nova_agent_api import get_nova_agent_api
from app.components.chat.dialogue_bar import Message, dialoguebar
from app.components.chat.input_bar import Parameters, inputbar
from app.components.common.baisc_components import basic_page

_SELECTED_MODELS = ["basic", "reasoning", "basic_no_thinking", "deepseek", "gemini"]
_TITLE = "Chat - llm"
_DEFAULT_INTRO = f"""Hi! I'm **{_TITLE}**, a helpful assistant."""
_MAX_MESSAGE_LENGTH = 50_000


class ChatState(rx.State):
    """聊天页面状态"""

    default_chat_name = "Nova"
    current_chat = "Nova"
    is_processing = False

    params_fields: list[Parameters] = []
    chat_instance: dict[str, list[Message]] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始状态
        self.params_fields: list[Parameters] = [
            Parameters(
                mkey="model",
                mtype="select",
                mvalue="basic",
                mvaluetype="str",
                mselected=_SELECTED_MODELS,
            ),
            Parameters(
                mkey="config",
                mtype="text_area",
                mvalue=json.dumps({"user_id": "merlin"}),
                mvaluetype="dict",
                mselected=None,
            ),
        ]
        self.chat_instance = {
            self.default_chat_name: [Message(role="assistant", content=_DEFAULT_INTRO)]
        }

    # 获得badge
    @rx.var
    def get_badge(self) -> str:
        """获得badge"""
        return _TITLE + " - " + self.current_chat

    # 创建会话窗口的提交事件
    @rx.event
    def submit_create_chat_instance(self, form_data: dict[str, Any]):
        new_chat_name = form_data["new_chat_name"]
        self.current_chat = new_chat_name
        self.chat_instance[new_chat_name] = [
            Message(role="assistant", content=_DEFAULT_INTRO)
        ]

    # 获得当前会话内容
    @rx.var
    def get_chat_instance(self) -> list[Message]:
        return self.chat_instance.get(self.current_chat, [])

    # 获得所有会话窗口名称
    @rx.var
    def get_chat_names(self) -> list[str]:
        return list(self.chat_instance.keys())

    # 设置当前会话窗口名称
    @rx.event
    def set_chat_name(self, name: str):
        self.current_chat = name

    # 删除会话窗口
    @rx.event
    def del_chat_instance(self, name: str):
        """Delete the current chat."""
        if name not in self.chat_instance:
            return
        del self.chat_instance[name]

        if len(self.chat_instance) == 0:
            self.chat_instance = {
                self.default_chat_name: [
                    Message(role="assistant", content=_DEFAULT_INTRO)
                ]
            }

        if self.current_chat not in self.chat_instance:
            self.current_chat = list(self.chat_instance.keys())[0]

    # 修改设置的提交事件
    @rx.event
    def submit_input_bar_settings(self, form_data: dict[str, Any]):
        try:
            for k, v in form_data.items():
                for item in self.params_fields:
                    if item.mkey == k:
                        if item.mvaluetype == "float":
                            item.mvalue = float(v)
                        elif item.mvaluetype == "int":
                            item.mvalue = int(v)
                        elif item.mvaluetype == "dict":
                            item.mvalue = json.dumps((json.loads(v)))
                        else:
                            item.mvalue = v
        except Exception as e:
            return rx.window_alert(str(e))

    # 对话框的提交事件
    @rx.event
    async def submit_input_bar_question(self, form_data: dict[str, Any]):
        question = form_data["question"]
        if not question:
            yield rx.window_alert("输入不能为空")
            return

        context = {"thread_id": self.current_chat}
        for item in self.params_fields:
            if item.mvaluetype == "dict":
                context[item.mkey] = json.loads(item.mvalue)
            elif item.mvaluetype == "int":
                context[item.mkey] = int(item.mvalue)
            elif item.mvaluetype == "float":
                context[item.mkey] = float(item.mvalue)
            else:
                context[item.mkey] = item.mvalue

        self.chat_instance[self.current_chat].append(
            Message(role="user", content=question)
        )
        self.is_processing = True
        messages = self._session_contxet_control_and_get_message()

        is_start_answer = True
        is_start_thinking = True
        uid4 = str(uuid.uuid4())

        # 初始化assistant的内容
        self.chat_instance[self.current_chat].append(
            Message(role="assistant", content="")
        )

        async for value in get_nova_agent_api(
            url_name="llm",
            trace_id=uid4,
            state={"messages": messages},
            context=context,
        ):
            if value and value.get("type", None) is not None:
                if value["type"] == "thought":
                    if is_start_thinking:
                        self.chat_instance[self.current_chat][
                            -1
                        ].content += "\n\n🤔 Thinking...\n\n"
                        is_start_thinking = False

                    self.chat_instance[self.current_chat][-1].content += value[
                        "content"
                    ]

                if value["type"] == "answer":
                    if is_start_answer:
                        self.chat_instance[self.current_chat][
                            -1
                        ].content += "\n\n✨ Answering...\n\n"
                        is_start_answer = False

                    self.chat_instance[self.current_chat][-1].content += value[
                        "content"
                    ]
                yield
        self.is_processing = False

    def _session_contxet_control_and_get_message(self):
        messages = []
        messages_len = 0
        for message in self.chat_instance[self.current_chat]:
            messages.append({"role": message.role, "content": message.content})
            messages_len += len(message.content)

        if messages_len > _MAX_MESSAGE_LENGTH:
            self.chat_instance[self.current_chat].pop(0)

        return messages


def chat_page_main():
    return rx.vstack(
        # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
        # 这一行是触发同步的“钩子”
        # rx.box(
        #     on_mount=ChatState.init_state,  # 页面加载时执行一次
        #     display="none",  # 完全隐藏，不影响布局
        # ),
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        rx.box(
            dialoguebar(ChatState.get_chat_instance),
            flex="1",  # 自动填充剩余高度
            overflow_y="auto",  # 消息过多时局部滚动
            overflow_x="hidden",
            padding_bottom="10px",  # 为输入栏预留空间
            width="100%",  # 对话栏占满宽度，保证内容左对齐/自适应
        ),
        rx.box(
            inputbar(
                _TITLE,
                ChatState.submit_create_chat_instance,
                ChatState.get_chat_names,
                ChatState.set_chat_name,
                ChatState.del_chat_instance,
                ChatState.submit_input_bar_question,
                ChatState.params_fields,
                ChatState.submit_input_bar_settings,
                ChatState.is_processing,
            ),
            # 关键：限制inputbar的宽度，否则100%宽度无法体现居中
            width="80%",  # 可根据需求调整为固定值（如600px）或百分比
            spacing="2",
            align_items="center",  # 子组件水平居中
            justify_content="center",  # 内部元素整体居中
            margin="0 auto",  # 兜底的CSS居中（增强兼容性）
        ),
        height="100%",
        width="100%",
        align_items="center",  # 核心：让vstack的所有子组件水平居中
        justify_content="space-between",  # 对话栏占满上方，输入栏在底部
        gap="1rem",  # 可选：增加子组件间距
    )


def chat_page() -> rx.Component:
    return basic_page(ChatState.get_badge, chat_page_main())
