# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import logging

import reflex as rx

logger = logging.getLogger(__name__)

_DEFAULT_NAME = "Nova"
_INTRODUCTION = "Hi! I'm **Nova**, a helpful assistant."
_SELECTED_MODELS = ["basic", "reasoning", "basic_no_thinking", "deepseek", "gemini"]
_TASK_DIR = "../merlin"
_PROMPT_DIR = "../prompts"
