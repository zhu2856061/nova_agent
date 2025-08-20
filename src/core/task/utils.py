# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import operator

from langchain_core.messages import (
    AIMessage,
    MessageLikeRepresentation,
    filter_messages,
)


def remove_up_to_last_ai_message(
    messages: list[MessageLikeRepresentation],
) -> list[MessageLikeRepresentation]:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            return messages[:i]
    return messages


def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    return [
        tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")
    ]


def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
