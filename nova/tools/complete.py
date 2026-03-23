# -*- coding: utf-8 -*-
# @Time   : 2026/02/13 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Todo(BaseModel):
    content: str
    status: Literal["pending", "in_progress", "completed"]


COMPLETE_TOOL_DESCRIPTION = """Call this tool to indicate that the task is complete."""


@tool("complete_tool", description=COMPLETE_TOOL_DESCRIPTION)
def complete_tool() -> str:
    """Call this tool to indicate that the research is complete."""
    return "complete"
