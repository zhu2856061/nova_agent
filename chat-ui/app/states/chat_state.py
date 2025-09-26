# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from dataclasses import dataclass, field
from typing import Any

import reflex as rx

from app.api.stream_llm_chat import get_stream_llm_response

logger = logging.getLogger(__name__)

_INTRODUCTION = "Hi! I'm **Nova Chat**, a helpful assistant."
_DEFAULT_NAME = "NovaChat"


@dataclass(kw_only=True)
class Message:
    """A message in the chat."""

    role: str = field(default="assistant")
    content: str = field(default="")


class ChatState(rx.State):
    """The app state."""

    # The current chat name.
    current_chat = _DEFAULT_NAME

    # A dict from the chat name to the list of questions and answers.
    _chats: dict[str, list[Message]] = {
        _DEFAULT_NAME: [Message(role="assistant", content=_INTRODUCTION)]
    }

    # Whether we are processing the question.
    processing: bool = False

    # Whether the new chat modal is open.
    is_modal_open: bool = False

    # params
    llm_dtype: str = "basic_no_thinking"
    config: dict = {}

    @rx.event
    def create_chat(self, form_data: dict[str, Any]):
        """Create a new chat."""
        # Add the new chat to the list of chats.
        new_chat_name = form_data["new_chat_name"]
        self.current_chat = new_chat_name
        self._chats[new_chat_name] = []
        self.is_modal_open = False

    @rx.event
    def set_is_modal_open(self, is_open: bool):
        """Set the new chat modal open state.

        Args:
            is_open: Whether the modal is open.
        """
        self.is_modal_open = is_open

    @rx.var
    def selected_chat(self) -> list[Message]:
        """Get the list of questions and answers for the current chat.

        Returns:
            The list of questions and answers.
        """
        return (
            self._chats[self.current_chat] if self.current_chat in self._chats else []
        )

    @rx.event
    def delete_chat(self, chat_name: str):
        """Delete the current chat."""
        if chat_name not in self._chats:
            return
        del self._chats[chat_name]
        if len(self._chats) == 0:
            self._chats = {
                _DEFAULT_NAME: [Message(role="assistant", content=_INTRODUCTION)],
            }
        if self.current_chat not in self._chats:
            self.current_chat = list(self._chats.keys())[0]

    @rx.event
    def set_chat(self, chat_name: str):
        """Set the name of the current chat.

        Args:
            chat_name: The name of the chat.
        """
        self.current_chat = chat_name

    @rx.var
    def chat_titles(self) -> list[str]:
        """Get the list of chat titles.

        Returns:
            The list of chat names.
        """
        return list(self._chats.keys())

    @rx.event
    async def process_question(self, form_data: dict[str, Any]):
        # Get the question from the form
        question = form_data["question"]

        # Check if the question is empty
        if not question:
            return

        self._chats[self.current_chat].append(Message(role="user", content=question))

        self.processing = True

        # Build the messages.
        messages = []
        for message in self._chats[self.current_chat]:
            messages.append({"role": message.role, "content": message.content})

        # 初始化
        self._chats[self.current_chat].append(Message(role="assistant"))

        async for value in get_stream_llm_response(
            self.current_chat, self.llm_dtype, messages, self.config
        ):  # type: ignore
            if value and value.get("type") == "answer":
                self._chats[self.current_chat][-1].content += value["content"]
                self._chats = self._chats

            yield

        # Toggle the processing flag.
        self.processing = False
