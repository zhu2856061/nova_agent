# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from typing import Any

import reflex as rx

from app.api.agent_api import STREAM_AGENT_RESEARCHER_BACKEND_URL, get_agent_api
from app.states.state import Message, Parameters, State

logger = logging.getLogger(__name__)

_INTRODUCTION = "Hi! I'm **Nova Agent Researcher**, a helpful assistant."
MAX_TOTAL_CHARS = 150000  # 总字符保护限制
_DEFAULT_NAME = "Nova"


class AgentResearcherState(State):
    unique_id = "Agent - Researcher"
    _default_introduction = _INTRODUCTION
    _default_name = _DEFAULT_NAME

    params_fields: list[Parameters] = [
        Parameters(
            mkey="researcher_model",
            mtype="select",
            mvalue="reasoning",
            mvaluetype="str",
            mselected=["basic", "reasoning", "basic_no_thinking"],
        ),
        Parameters(
            mkey="summarize_model",
            mtype="select",
            mvalue="reasoning",
            mvaluetype="str",
            mselected=["basic", "reasoning", "basic_no_thinking"],
        ),
        Parameters(
            mkey="compress_research_model",
            mtype="select",
            mvalue="reasoning",
            mvaluetype="str",
            mselected=["basic", "reasoning", "basic_no_thinking"],
        ),
        Parameters(
            mkey="max_react_tool_calls",
            mtype="text",
            mvalue=2,
            mvaluetype="int",
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
        logger.info(f"change settings, {self.params_fields}")

    @rx.event
    def create_chat(self, form_data: dict[str, Any]):
        """Create a new chat."""
        # Add the new chat to the list of chats.
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
        config = {}
        for item in self.params_fields:
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

        full_response = ""
        _content_len = 0

        async for item in get_agent_api(
            STREAM_AGENT_RESEARCHER_BACKEND_URL,
            self.current_chat,
            {"researcher_messages": messages},
            config,
        ):  # type: ignore
            content = item["content"]
            full_response += str(content)  # 累加完整响应
            if len(full_response) >= MAX_TOTAL_CHARS:
                full_response += "\n\n⚠️ 已达到最大字符限制，后续内容已截断。"
                continue  # 终止流式处理

            # 🔹 处理 System 消息（如任务状态、工具调用）
            if item["type"] in ["system", "error"]:
                if item["type"] == "error":
                    self._chat2messages[self.current_chat][
                        -1
                    ].content += f"<span style='color:red'>{content}</span>"

                else:
                    self._chat2messages[self.current_chat][-1].content += content

            elif item["type"] == "chat_start":
                self._chat2messages[self.current_chat][-1].content += content

            elif item["type"] == "chat_end":
                if isinstance(content, dict):
                    _reasoning_content = content["reasoning_content"]
                    _content = content["content"]
                    _tool_calls = content["tool_calls"]
                    print(content)

                    if _content_len > 0:
                        self._chat2messages[self.current_chat][
                            -1
                        ].content = self._chat2messages[self.current_chat][-1].content[
                            :-_content_len
                        ]
                        _content_len = 0

                    if _reasoning_content:
                        self._chat2messages[self.current_chat][
                            -1
                        ].content += f"📝 思考过程\n\n{_reasoning_content}\n\n"

                    if _tool_calls:
                        self._chat2messages[self.current_chat][
                            -1
                        ].content += f"📝 工具入参\n\n{_tool_calls}\n\n"

                    if _content.strip():
                        self._chat2messages[self.current_chat][
                            -1
                        ].content += f"📘 【Answer】\n\n{_content} \n\n"

            elif item["type"] == "answer":
                self._chat2messages[self.current_chat][-1].content += content
                _content_len += len(content)

            elif item["type"] == "thought":
                self._chat2messages[self.current_chat][-1].content += content
                _content_len += len(content)

            yield

        # Toggle the processing flag.
        self.processing = False
