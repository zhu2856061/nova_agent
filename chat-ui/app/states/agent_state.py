# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from dataclasses import dataclass, field
from typing import Any

import reflex as rx

from app.api.stream_agent_memorizer import get_stream_agent_response

logger = logging.getLogger(__name__)

_INTRODUCTION = "Hi! I'm **Nova Agent**, a helpful assistant."
MAX_TOTAL_CHARS = 150000  # 总字符保护限制
_DEFAULT_NAME = "NovaAgent"


@dataclass(kw_only=True)
class Message:
    """A message in the chat."""

    role: str = field(default="assistant")
    content: str = field(default="")


class AgentState(rx.State):
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

    current_agent_name = "memorizer"

    agent_names = [
        "memorizer",
        "searcher",
    ]

    # params
    llm_dtype: str = "basic"
    config: dict = {}

    @rx.event
    def create_chat(self, form_data: dict[str, Any]):
        """Create a new chat."""
        # Add the new chat to the list of chats.
        new_chat_name = form_data["new_chat_name"]
        self.current_chat = new_chat_name
        self._chats[new_chat_name] = [Message(role="assistant", content=_INTRODUCTION)]
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

        full_response = ""
        _content_len = 0

        async for item in get_stream_agent_response(
            self.current_chat, self.llm_dtype, messages, self.config
        ):  # type: ignore
            content = item["content"]
            full_response += str(content)  # 累加完整响应
            if len(full_response) >= MAX_TOTAL_CHARS:
                full_response += "\n\n⚠️ 已达到最大字符限制，后续内容已截断。"
                continue  # 终止流式处理

            # 🔹 处理 System 消息（如任务状态、工具调用）
            if item["type"] in ["system", "error"]:
                if item["type"] == "error":
                    self._chats[self.current_chat][
                        -1
                    ].content += f"<span style='color:red'>{content}</span>"

                else:
                    self._chats[self.current_chat][-1].content += content

            elif item["type"] == "chat_start":
                self._chats[self.current_chat][-1].content += content

            elif item["type"] == "chat_end":
                if isinstance(content, dict):
                    _reasoning_content = content["reasoning_content"]
                    _content = content["content"]
                    _tool_calls = content["tool_calls"]
                    print(content)

                    if _content_len > 0:
                        self._chats[self.current_chat][-1].content = self._chats[
                            self.current_chat
                        ][-1].content[:-_content_len]
                        _content_len = 0

                    if _reasoning_content:
                        self._chats[self.current_chat][
                            -1
                        ].content += f"📝 思考过程\n\n{_reasoning_content}\n\n"

                    if _tool_calls:
                        self._chats[self.current_chat][
                            -1
                        ].content += f"📝 工具入参\n\n{_tool_calls}\n\n"

                    if _content.strip():
                        self._chats[self.current_chat][
                            -1
                        ].content += f"📘 【Answer】\n\n{_content} \n\n"

            elif item["type"] == "answer":
                self._chats[self.current_chat][-1].content += content
                _content_len += len(content)

            elif item["type"] == "thought":
                self._chats[self.current_chat][-1].content += content
                _content_len += len(content)

            yield

        # Toggle the processing flag.
        self.processing = False
