# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import List, Literal

from nova.model.agent import Todo
from nova.sandbox.local.utils import (
    build_grep_results_dict,
    clean_markdown_links,
    format_content_with_line_numbers,
    format_grep_results,
    get_shell,
    list_dir,
    perform_string_replacement,
    python_search,
    resolve_path,
    ripgrep_search,
    truncate_if_too_long,
    validate_path,
)
from nova.sandbox.sandbox import Sandbox
from nova.tools.baidu_serper import SerpBaiduTool
from nova.tools.web_crawler import CrawlTool

logger = logging.getLogger(__name__)


class LocalSandbox(Sandbox):
    def __init__(self, id: str, path_mappings: dict[str, str] | None = None):
        """
        Initialize local sandbox with optional path mappings.

        Args:
            id: Sandbox identifier
            path_mappings: Dictionary mapping container paths to local paths
                          Example: {"/mnt/skills": "/absolute/path/to/skills"}
        """
        super().__init__(id)
        self.path_mappings = path_mappings or {}

    def _reverse_resolve_path(self, path: str) -> str:
        """
        Reverse resolve local path back to container path using mappings.

        Args:
            path: Local path that might need to be mapped to container path

        Returns:
            Container path if mapping exists, otherwise original path
        """
        path_str = str(Path(path).resolve())

        # Try each mapping (longest local path first for more specific matches)
        for container_path, local_path in sorted(
            self.path_mappings.items(), key=lambda x: len(x[1]), reverse=True
        ):
            local_path_resolved = str(Path(local_path).resolve())
            if path_str.startswith(local_path_resolved):
                # Replace the local path prefix with container path
                relative = path_str[len(local_path_resolved) :].lstrip("/")
                resolved = (
                    f"{container_path}/{relative}" if relative else container_path
                )
                return resolved

        # No mapping found, return original path
        return path_str

    def _reverse_resolve_paths_in_output(self, output: str) -> str:
        """
        Reverse resolve local paths back to container paths in output string.

        Args:
            output: Output string that may contain local paths

        Returns:
            Output with local paths resolved to container paths
        """
        import re

        # Sort mappings by local path length (longest first) for correct prefix matching
        sorted_mappings = sorted(
            self.path_mappings.items(), key=lambda x: len(x[1]), reverse=True
        )

        if not sorted_mappings:
            return output

        # Create pattern that matches absolute paths
        # Match paths like /Users/... or other absolute paths
        result = output
        for container_path, local_path in sorted_mappings:
            local_path_resolved = str(Path(local_path).resolve())
            # Escape the local path for use in regex
            escaped_local = re.escape(local_path_resolved)
            # Match the local path followed by optional path components
            pattern = re.compile(escaped_local + r"(?:/[^\s\"';&|<>()]*)?")

            def replace_match(match: re.Match) -> str:
                matched_path = match.group(0)
                return self._reverse_resolve_path(matched_path)

            result = pattern.sub(replace_match, result)

        return result

    def _resolve_paths_in_command(self, command: str) -> str:
        """
        Resolve container paths to local paths in a command string.

        Args:
            command: Command string that may contain container paths

        Returns:
            Command with container paths resolved to local paths
        """
        import re

        # Sort mappings by length (longest first) for correct prefix matching
        sorted_mappings = sorted(
            self.path_mappings.items(), key=lambda x: len(x[0]), reverse=True
        )

        # Build regex pattern to match all container paths
        # Match container path followed by optional path components
        if not sorted_mappings:
            return command

        # Create pattern that matches any of the container paths
        patterns = [
            re.escape(container_path) + r"(?:/[^\s\"';&|<>()]*)??"
            for container_path, _ in sorted_mappings
        ]
        pattern = re.compile("|".join(f"({p})" for p in patterns))

        def replace_match(match: re.Match) -> str:
            matched_path = match.group(0)
            return str(resolve_path(matched_path))

        return pattern.sub(replace_match, command)

    def read_file(self, file_path: str, offset: int, limit: int) -> str:
        # 判断路径
        validated_path = validate_path(file_path)

        # 确定路径
        validated_path = resolve_path(validated_path)

        if not validated_path.exists() or not validated_path.is_file():
            return f"Error: File '{file_path}' not found"

        try:
            # 尽可能使用O_NOFOLLOW标志打开文件以避免符号链接遍历
            fd = os.open(validated_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read()
            if not content or content.strip() == "":
                return "System reminder: File exists but has empty contents"

            # 取指定位置的内容
            lines = content.splitlines()
            start_idx = offset
            end_idx = min(start_idx + limit, len(lines))
            if start_idx >= len(lines):
                return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"
            selected_lines = lines[start_idx:end_idx]

            # 形式化数据
            return format_content_with_line_numbers(
                selected_lines, start_line=start_idx + 1
            )
        except (OSError, PermissionError) as e:
            return f"Error reading file '{file_path}': {e}"

    def write_file(self, file_path: str, content: str, append: bool = False) -> str:
        # 判断路径
        validated_path = validate_path(file_path)

        # 确定路径
        validated_path = resolve_path(validated_path)

        if validated_path.exists():
            return f"Cannot write to {file_path} because it already exists. Read and then make an edit, or write to a new path."

        try:
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(validated_path, flags, 0o644)
            mode = "a" if append else "w"
            with os.fdopen(fd, mode, encoding="utf-8") as f:
                f.write(content)

            return f"Wrote file {file_path}"

        except (OSError, PermissionError) as e:
            return f"Error writing file '{file_path}': {e}"

    def edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """Write content to a file.

        Args:
            file_path: The absolute path of the file to write to.
            content: The text content to write to the file.
            append: Whether to append the content to the file. If False, the file will be created or overwritten.
        """
        # 判断路径
        validated_path = validate_path(file_path)

        # 确定路径
        validated_path = resolve_path(validated_path)

        if not validated_path.exists() or not validated_path.is_file():
            return f"Error: File '{file_path}' not found"

        try:
            fd = os.open(validated_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read()

            if not content or content.strip() == "":
                return (
                    f"System reminder: File '{file_path}' exists but has empty contents"
                )

            result = perform_string_replacement(
                content, old_string, new_string, replace_all
            )
            new_content, occurrences = result

            # Write securely
            flags = os.O_WRONLY | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(validated_path, flags)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully replaced {int(occurrences)} instance(s) of the string in '{file_path}'"

        except (OSError, PermissionError) as e:
            return f"Error editing file '{file_path}': {e}"

    def ls(self, path: str) -> str:
        # 判断路径
        validated_path = validate_path(path)

        # 确定路径
        validated_path = resolve_path(validated_path)

        if not validated_path.exists() or not validated_path.is_dir():
            return f"Error: dir '{path}' not found"

        try:
            result = list_dir(str(validated_path))

            result = truncate_if_too_long(result)

            if not result:
                return "(empty)"
            return "\n".join(result)

        except (OSError, PermissionError) as e:
            return f"Error ls dir '{path}': {e}"

    def glob(self, pattern: str, path: str = "/") -> str:
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")

        # 判断路径
        validated_path = validate_path(path)

        # 确定路径
        validated_path = resolve_path(validated_path)

        if not validated_path.exists() or not validated_path.is_dir():
            return f"Error: File '{path}' not found"
        try:
            result = []
            for matched_path in validated_path.rglob(pattern):
                try:
                    is_file = matched_path.is_file()
                except OSError:
                    continue
                if not is_file:
                    continue

                abs_path = str(matched_path)
                result.append(abs_path)
            result = truncate_if_too_long(result)

            if not result:
                return "(empty)"
            return "\n".join(result)

        except (OSError, PermissionError) as e:
            return f"Error glob dir '{path}': {e}"

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        output_mode: Literal[
            "files_with_matches", "content", "count"
        ] = "files_with_matches",
    ) -> str:
        # 判断路径
        validated_path = validate_path(path or ".")

        # 确定路径
        validated_path = resolve_path(validated_path)

        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        if not validated_path.exists():
            return f"Error: File '{path}' not found"
        results = ripgrep_search(pattern, validated_path, glob)

        if results is None:
            results = python_search(pattern, validated_path, glob)

        matches = []
        for fpath, items in results.items():
            for line_num, line_text in items:
                matches.append(
                    {"path": fpath, "line": int(line_num), "text": line_text}
                )

        if not matches:
            return "No matches found"

        formatted = format_grep_results(build_grep_results_dict(matches), output_mode)
        formatted = truncate_if_too_long(formatted)
        if not formatted:
            return "(empty)"

        return str(formatted)

    def execute(self, command: str) -> str:
        # Resolve container paths in command before execution
        resolved_command = self._resolve_paths_in_command(command)

        result = subprocess.run(
            resolved_command,
            executable=get_shell(),
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nStd Error:\n{result.stderr}" if output else result.stderr
        if result.returncode != 0:
            output += f"\nExit Code: {result.returncode}"

        final_output = output if output else "(no output)"
        # Reverse resolve local paths back to container paths in output
        return self._reverse_resolve_paths_in_output(final_output)

    async def web_search(self, queries: List[str]) -> str:
        logger.info(f"开始网络检索：检索词: {queries}")

        serp_tool = SerpBaiduTool()
        crawl_tool = CrawlTool()
        # 获取搜索结果
        search_tasks = []
        for query in queries:
            search_tasks.append(serp_tool.arun({"query": query, "max_results": 3}))
        search_results = await asyncio.gather(*search_tasks)

        unique_results = {}
        for response in search_results:
            for result in response["result"]:
                url = result["link"]
                if url not in unique_results:
                    unique_results[url] = {**result, "query": response["query"]}

        logger.info(f"Search results size: {len(unique_results)}")

        # 获取网站内容
        crawl_tasks = [
            crawl_tool.arun({"url": url}) for url, result in unique_results.items()
        ]
        crawl_results = await asyncio.gather(*crawl_tasks)

        for response in crawl_results:
            url = response["url"]
            result = response["result"]
            if url in unique_results:
                text = " ".join(
                    [
                        clean_markdown_links(tx["text"])
                        for tx in result["content"]
                        if tx["type"] == "text"
                    ]
                )

                unique_results[url]["raw_content"] = text

        # 汇总信息
        all_info = []
        for result in unique_results.values():
            all_info.append(
                f"**query**: {result['query']}\n\n**title**: {result['title']}\n\n**abstract**: {result['abstract']}\n\n**content**: {result['raw_content']}\n"
            )

        logger.info(f"网络检索完成，检索结果数量: {len(all_info)}")
        return "\n\n---\n\n".join(all_info)

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
        return f"Clarification request processed by middleware, question: {question}, clarification_type: {clarification_type}, reason: {context}"

    def create_subtask(
        self,
        description: str,
        prompt: str,
        subagent_type: Literal["general-purpose"] | Literal["bash"],
        max_turns: int | None = None,
    ) -> str:
        return ""

    def todo_list(self, todos: list[Todo]) -> str:
        return f"Updated todo list to {todos}"
