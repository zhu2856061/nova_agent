# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from .context_summarize import compile_context_summarize_agent
from .webpage_summarize import compile_webpage_summarize_agent

context_summarize = compile_context_summarize_agent()
webpage_summarize = compile_webpage_summarize_agent()
