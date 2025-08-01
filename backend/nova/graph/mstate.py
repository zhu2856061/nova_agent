# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

from langchain_core.messages import AIMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated, TypedDict


# ⏱️
class OverallState(TypedDict):
    messages: Annotated[list, add_messages]
    # -> supervisor variables
    question: str
    answer: AIMessage
    step: int
