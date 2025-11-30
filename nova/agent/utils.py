# -*- coding: utf-8 -*-
# @Time   : 2025/11/29 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

from langchain_core.messages import BaseMessage


def extract_valid_info(response: BaseMessage):
    if "tool_calls" in response.additional_kwargs:
        response.additional_kwargs.pop("tool_calls")
