# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from .ask_clarification import ask_clarification_tool
from .digital_human_manager import (
    sandbox_edit_file_tool,
    sandbox_execute_tool,
    sandbox_glob_tool,
    sandbox_grep_tool,
    sandbox_ls_tool,
    sandbox_read_file_tool,
    sandbox_write_file_tool,
)
from .web_wechat_search import (
    web_crawl,
    web_search,
)
from .write_todos import write_todos_tool

# 数字人核心工具
Digital_Human_Manager = {
    # "create_subagent": create_subagent_tool,
    "read_file": sandbox_read_file_tool,
    "write_file": sandbox_write_file_tool,
    "edit_file": sandbox_edit_file_tool,
    "ls": sandbox_ls_tool,
    "glob": sandbox_glob_tool,
    "grep": sandbox_grep_tool,
    "execute": sandbox_execute_tool,
    "ask_clarification": ask_clarification_tool,
    "write_todos": write_todos_tool,
    "web_search": web_search,
    "fetch_url": web_crawl,
}
