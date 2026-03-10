# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Literal, Optional


class Sandbox(ABC):
    """Abstract base class for sandbox environments"""

    _id: str

    def __init__(self, id: str):
        self._id = id

    @property
    def id(self) -> str:
        return self._id

    @abstractmethod
    def read_file(self, file_path: str, offset: int, limit: int) -> str:
        """Read the content of a file.

        Args:
            path: The absolute path of the file to read.

        Returns:
            The content of the file.
        """
        pass

    @abstractmethod
    def write_file(self, file_path: str, content: str, append: bool = False) -> None:
        """Write content to a file.

        Args:
            path: The absolute path of the file to write to.
            content: The text content to write to the file.
            append: Whether to append the content to the file. If False, the file will be created or overwritten.
        """
        pass

    @abstractmethod
    def edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> int:
        """Write content to a file.

        Args:
            file_path: The absolute path of the file to write to.
            content: The text content to write to the file.
            append: Whether to append the content to the file. If False, the file will be created or overwritten.
        """
        pass

    @abstractmethod
    def ls(self, path: str) -> str:
        """列出指定目录下的文件、子目录名称，以及它们的属性（如权限、大小、修改时间等）"""
        pass

    @abstractmethod
    def glob(self, pattern: str, path: str = "/") -> str:
        """用于文件路径匹配 / 通配的核心工具，它能按指定的模式快速查找符合条件的文件 / 目录"""
        pass

    @abstractmethod
    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        output_mode: Literal[
            "files_with_matches", "content", "count"
        ] = "files_with_matches",
    ) -> str:
        """在文件或输入流中搜索匹配指定字符串 / 正则表达式的行，并输出这些行
        命令行里的 “查找 / 搜索” 工具，支持精准匹配、模糊匹配、正则匹配等多种方式
        """
        pass

    @abstractmethod
    def execute(self, command: str) -> str:
        """Execute bash command in sandbox.

        Args:
            command: The command to execute.

        Returns:
            The standard or error output of the command.
        """
        pass

    @abstractmethod
    async def web_search(
        self, queries: List[str], summarize_model: Optional[str] = None
    ) -> str:
        """网络搜索功能"""
        pass

    @abstractmethod
    async def fetch_url(self, url: str, timeout: int = 30) -> str:
        """网络抓取功能"""
        pass

    @abstractmethod
    def ask_clarification(
        self,
        question: str,
        clarification_type: Literal[
            "missing_info",
            "ambiguous_requirement",
            "approach_choice",
            "risk_confirmation",
            "suggestion",
        ],
        context: str | None = None,
        options: list[str] | None = None,
    ) -> str:
        return f"Clarification:\n\nquestion: {question}\n\nclarification_type: {clarification_type}\n\nreason: {context}\n\noptions: {options}"

    @abstractmethod
    def create_subtask(
        self,
        description: str,
        prompt: str,
        subagent_type: Literal["general-purpose", "bash"],
        max_turns: int | None = None,
    ):
        pass

    @abstractmethod
    def todo_list(self, todos: list) -> str:
        return f"Updated todo list to {todos}"


class SandboxProvider(ABC):
    """Abstract base class for sandbox providers"""

    @abstractmethod
    def acquire(self, thread_id: str | None = None) -> str:
        """Acquire a sandbox environment and return its ID.

        Returns:
            The ID of the acquired sandbox environment.
        """
        pass

    @abstractmethod
    def get(self, sandbox_id: str) -> Sandbox | None:
        """Get a sandbox environment by ID.

        Args:
            sandbox_id: The ID of the sandbox environment to retain.
        """
        pass

    @abstractmethod
    def release(self, sandbox_id: str) -> None:
        """Release a sandbox environment.

        Args:
            sandbox_id: The ID of the sandbox environment to destroy.
        """
        pass
