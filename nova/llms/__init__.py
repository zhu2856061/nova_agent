# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .llm import LLMSProvider
from .template import PromptsProvider

# 全局变量
LLMS_Provider_Instance = LLMSProvider(CONF.LLM)
Prompts_Provider_Instance = PromptsProvider(CONF.SYSTEM.prompt_template_dir)
