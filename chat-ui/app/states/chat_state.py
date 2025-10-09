# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import Any

import reflex as rx

from app.api.chat_api import STREAM_CHAT_BACKEND_URL, get_chat_api
from app.states.state import Message, Parameters, State, _SELECTED_MODELS

logger = logging.getLogger(__name__)

_INTRODUCTION = "Hi! I'm **Nova Chat**, a helpful assistant."
MAX_TOTAL_CHARS = 150000  # 总字符保护限制
_DEFAULT_NAME = "Nova"


class ChatState(State):
    unique_id = "Chat"
    _default_introduction = _INTRODUCTION
    _default_name = _DEFAULT_NAME

    params_fields: list[Parameters] = [
        Parameters(
            mkey="llm_type",
            mtype="select",
            mvalue="basic",
            mvaluetype="str",
            mselected=_SELECTED_MODELS,
        ),
        Parameters(
            mkey="temperature",
            mtype="text",
            mvalue=0.2,
            mvaluetype="float",
            mselected=None,
        ),
    ]

    current_chat = _default_name

    _chat2messages: dict[str, list[Message]] = {
        _default_name: [Message(role="assistant", content=_default_introduction)]
    }

    @rx.event
    def update_params_fields(self, form_data: dict[str, Any]):
        for k, v in form_data.items():
            for item in self.params_fields:
                if item.mkey == k:
                    if item.mvaluetype == "float":
                        item.mvalue = float(v)
                    elif item.mvaluetype == "int":
                        item.mvalue = int(v)
                    else:
                        item.mvalue = v

    @rx.event
    def create_chat(self, form_data: dict[str, Any]):
        new_chat_name = form_data["new_chat_name"]
        self.current_chat = new_chat_name
        self._chat2messages[new_chat_name] = [
            Message(role="assistant", content=self._default_introduction)
        ]
        self.is_new_chat_modal_open = False

    @rx.var
    def show_chat_content(self) -> list[Message]:
        return (
            self._chat2messages[self.current_chat]
            if self.current_chat in self._chat2messages
            else []
        )

    @rx.event
    def delete_chat(self, name: str):
        """Delete the current chat."""
        if name not in self._chat2messages:
            return
        del self._chat2messages[name]

        if len(self._chat2messages) == 0:
            self._chat2messages = {
                self._default_name: [
                    Message(role="assistant", content=self._default_introduction)
                ],
            }

        if self.current_chat not in self._chat2messages:
            self.current_chat = list(self._chat2messages.keys())[0]

    @rx.event
    def set_chat_name(self, name: str):
        self.current_chat = name

    @rx.var
    def get_chat_names(self) -> list[str]:
        return list(self._chat2messages.keys())

    @rx.event
    async def process_question(self, form_data: dict[str, Any]):
        question = form_data["question"]
        if not question:
            return

        # get llm type
        _llm_type = "basic"
        config = {}
        for item in self.params_fields:
            if item.mkey == "llm_type":
                _llm_type = item.mvalue
                continue
            config[item.mkey] = item.mvalue

        self._chat2messages[self.current_chat].append(
            Message(role="user", content=question)
        )

        self.processing = True

        # Build the messages.
        messages = []
        for message in self._chat2messages[self.current_chat]:
            messages.append({"role": message.role, "content": message.content})

        # 初始化
        self._chat2messages[self.current_chat].append(Message(role="assistant"))

        is_start_answer = True
        is_start_thinking = True
        async for value in get_chat_api(
            STREAM_CHAT_BACKEND_URL,
            self.current_chat,
            _llm_type,
            messages,
            config,
        ):  # type: ignore
            if value and value.get("type") == "thought":
                if is_start_thinking:
                    self._chat2messages[self.current_chat][
                        -1
                    ].content += "\n\n🤔 Thinking...\n\n"
                    is_start_thinking = False

                self._chat2messages[self.current_chat][-1].content += value["content"]
                self._chat2messages = self._chat2messages

            if value and value.get("type") == "answer":
                if is_start_answer:
                    self._chat2messages[self.current_chat][
                        -1
                    ].content += "\n\n✨ Answering...\n\n"
                    is_start_answer = False

                self._chat2messages[self.current_chat][-1].content += value["content"]
                self._chat2messages = self._chat2messages

            yield

        # Toggle the processing flag.
        self.processing = False
