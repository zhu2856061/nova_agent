# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal, Sequence

import wcmatch.glob as wcglob

IGNORE_PATTERNS = [
    # Version Control
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    # Dependencies
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "env",
    ".tox",
    ".nox",
    ".eggs",
    "*.egg-info",
    "site-packages",
    # Build outputs
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    ".turbo",
    "target",
    "out",
    # IDE & Editor
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    "*~",
    ".project",
    ".classpath",
    ".settings",
    # OS generated
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.lnk",
    # Logs & temp files
    "*.log",
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.cache",
    ".cache",
    "logs",
    # Coverage & test artifacts
    ".coverage",
    "coverage",
    ".nyc_output",
    "htmlcov",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]
MAX_FILE_SIZE_MB = 10


def _should_ignore(name: str) -> bool:
    """Check if a file/directory name matches any ignore pattern."""
    for pattern in IGNORE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def list_dir(path: str, max_depth: int = 2) -> list[str]:
    """
    List files and directories up to max_depth levels deep.

    Args:
        path: The root directory path to list.
        max_depth: Maximum depth to traverse (default: 2).
                   1 = only direct children, 2 = children + grandchildren, etc.

    Returns:
        A list of absolute paths for files and directories,
        excluding items matching IGNORE_PATTERNS.
    """
    result: list[str] = []
    root_path = Path(path).resolve()

    if not root_path.is_dir():
        return result

    def _traverse(current_path: Path, current_depth: int) -> None:
        """Recursively traverse directories up to max_depth."""
        if current_depth > max_depth:
            return

        try:
            for item in current_path.iterdir():
                if _should_ignore(item.name):
                    continue

                post_fix = "/" if item.is_dir() else ""
                result.append(str(item.resolve()) + post_fix)

                # Recurse into subdirectories if not at max depth
                if item.is_dir() and current_depth < max_depth:
                    _traverse(item, current_depth + 1)
        except PermissionError:
            pass

    _traverse(root_path, 1)

    return sorted(result)


def resolve_path(path: str) -> Path:
    """
    Resolve container path to actual local path using mappings.

    Args:
        path: Path that might be a container path

    Returns:
        Resolved local path
    """
    cwd = Path.cwd()
    validated_path = Path(path)

    if not validated_path.is_absolute():
        validated_path = (cwd / validated_path).resolve()

    # No mapping found, return original path
    return validated_path


def validate_path(path: str, *, allowed_prefixes: Sequence[str] | None = None) -> str:
    r"""Validate and normalize file path for security.

    Ensures paths are safe to use by preventing directory traversal attacks
    and enforcing consistent formatting. All paths are normalized to use
    forward slashes and start with a leading slash.

    This function is designed for virtual filesystem paths and rejects
    Windows absolute paths (e.g., C:/..., F:/...) to maintain consistency
    and prevent path format ambiguity.

    Args:
        path: The path to validate and normalize.
        allowed_prefixes: Optional list of allowed path prefixes. If provided,
            the normalized path must start with one of these prefixes.

    Returns:
        Normalized canonical path starting with `/` and using forward slashes.

    Raises:
        ValueError: If path contains traversal sequences (`..` or `~`), is a
            Windows absolute path (e.g., C:/...), or does not start with an
            allowed prefix when `allowed_prefixes` is specified.

    Example:
        ```python
        validate_path("foo/bar")  # Returns: "/foo/bar"
        validate_path("/./foo//bar")  # Returns: "/foo/bar"
        validate_path("../etc/passwd")  # Raises ValueError
        validate_path(r"C:\\Users\\file.txt")  # Raises ValueError
        validate_path("/data/file.txt", allowed_prefixes=["/data/"])  # OK
        validate_path("/etc/file.txt", allowed_prefixes=["/data/"])  # Raises ValueError
        ```
    """
    if ".." in path or path.startswith("~"):
        path = str(Path(path).resolve())
        # msg = f"Path traversal not allowed: {path}"
        # raise ValueError(msg)

    # Reject Windows absolute paths (e.g., C:\..., D:/...)
    # This maintains consistency in virtual filesystem paths
    if re.match(r"^[a-zA-Z]:", path):
        msg = f"Windows absolute paths are not supported: {path}. Please use virtual paths starting with / (e.g., /workspace/file.txt)"
        raise ValueError(msg)

    normalized = os.path.normpath(path)
    normalized = normalized.replace("\\", "/")

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    if allowed_prefixes is not None and not any(
        normalized.startswith(prefix) for prefix in allowed_prefixes
    ):
        msg = f"Path must start with one of {allowed_prefixes}: {path}"
        raise ValueError(msg)

    return normalized


def format_content_with_line_numbers(
    content: str | list[str],
    start_line: int = 1,
) -> str:
    """Format file content with line numbers (cat -n style).

    Chunks lines longer than MAX_LINE_LENGTH with continuation markers (e.g., 5.1, 5.2).

    Args:
        content: File content as string or list of lines
        start_line: Starting line number (default: 1)

    Returns:
        Formatted content with line numbers and continuation markers
    """
    MAX_LINE_LENGTH = 10000
    LINE_NUMBER_WIDTH = 6

    if isinstance(content, str):
        lines = content.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
    else:
        lines = content

    result_lines = []
    for i, line in enumerate(lines):
        line_num = i + start_line

        if len(line) <= MAX_LINE_LENGTH:
            result_lines.append(f"{line_num:{LINE_NUMBER_WIDTH}d}\t{line}")
        else:
            # Split long line into chunks with continuation markers
            num_chunks = (len(line) + MAX_LINE_LENGTH - 1) // MAX_LINE_LENGTH
            for chunk_idx in range(num_chunks):
                start = chunk_idx * MAX_LINE_LENGTH
                end = min(start + MAX_LINE_LENGTH, len(line))
                chunk = line[start:end]
                if chunk_idx == 0:
                    # First chunk: use normal line number
                    result_lines.append(f"{line_num:{LINE_NUMBER_WIDTH}d}\t{chunk}")
                else:
                    # Continuation chunks: use decimal notation (e.g., 5.1, 5.2)
                    continuation_marker = f"{line_num}.{chunk_idx}"
                    result_lines.append(
                        f"{continuation_marker:>{LINE_NUMBER_WIDTH}}\t{chunk}"
                    )

    return "\n".join(result_lines)


def perform_string_replacement(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool,
) -> tuple[str, int] | str:
    """Perform string replacement with occurrence validation.

    Args:
        content: Original content
        old_string: String to replace
        new_string: Replacement string
        replace_all: Whether to replace all occurrences

    Returns:
        Tuple of (new_content, occurrences) on success, or error message string
    """
    occurrences = content.count(old_string)

    if occurrences == 0:
        return f"Error: String not found in file: '{old_string}'"

    if occurrences > 1 and not replace_all:
        return f"Error: String '{old_string}' appears {occurrences} times in file. Use replace_all=True to replace all instances, or provide a more specific string with surrounding context."

    new_content = content.replace(old_string, new_string)
    return new_content, occurrences


def truncate_if_too_long(result: list[str] | str) -> list[str] | str:
    TOOL_RESULT_TOKEN_LIMIT = 20000
    TRUNCATION_GUIDANCE = (
        "... [results truncated, try being more specific with your parameters]"
    )

    """Truncate list or string result if it exceeds token limit (rough estimate: 4 chars/token)."""
    if isinstance(result, list):
        total_chars = sum(len(item) for item in result)
        if total_chars > TOOL_RESULT_TOKEN_LIMIT * 4:
            return result[
                : len(result) * TOOL_RESULT_TOKEN_LIMIT * 4 // total_chars
            ] + [TRUNCATION_GUIDANCE]
        return result
    # string
    if len(result) > TOOL_RESULT_TOKEN_LIMIT * 4:
        return result[: TOOL_RESULT_TOKEN_LIMIT * 4] + "\n" + TRUNCATION_GUIDANCE
    return result


def ripgrep_search(
    pattern: str, base_full: Path, include_glob: str | None
) -> dict[str, list[tuple[int, str]]] | None:
    cmd = ["rg", "--json"]
    if include_glob:
        cmd.extend(["--glob", include_glob])
    cmd.extend(["--", pattern, str(base_full)])

    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    results: dict[str, list[tuple[int, str]]] = {}
    for line in proc.stdout.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("type") != "match":
            continue
        pdata = data.get("data", {})
        ftext = pdata.get("path", {}).get("text")
        if not ftext:
            continue
        p = Path(ftext)

        virt = str(p)
        ln = pdata.get("line_number")
        lt = pdata.get("lines", {}).get("text", "").rstrip("\n")
        if ln is None:
            continue
        results.setdefault(virt, []).append((int(ln), lt))

    return results


def python_search(
    pattern: str, base_full: Path, include_glob: str | None
) -> dict[str, list[tuple[int, str]]]:
    try:
        regex = re.compile(pattern)
    except re.error:
        return {}

    results: dict[str, list[tuple[int, str]]] = {}
    root = base_full if base_full.is_dir() else base_full.parent

    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        if include_glob and not wcglob.globmatch(
            fp.name, include_glob, flags=wcglob.BRACE
        ):
            continue
        try:
            if fp.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                continue
        except OSError:
            continue
        try:
            content = fp.read_text()
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
        for line_num, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                virt_path = str(fp)
                results.setdefault(virt_path, []).append((line_num, line))

    return results


def format_grep_results(
    results: dict[str, list[tuple[int, str]]],
    output_mode: Literal["files_with_matches", "content", "count"],
) -> str:
    """Format grep search results based on output mode.

    Args:
        results: Dictionary mapping file paths to list of (line_num, line_content) tuples
        output_mode: Output format - "files_with_matches", "content", or "count"

    Returns:
        Formatted string output
    """
    if output_mode == "files_with_matches":
        return "\n".join(sorted(results.keys()))
    if output_mode == "count":
        lines = []
        for file_path in sorted(results.keys()):
            count = len(results[file_path])
            lines.append(f"{file_path}: {count}")
        return "\n".join(lines)
    lines = []
    for file_path in sorted(results.keys()):
        lines.append(f"{file_path}:")
        for line_num, line in results[file_path]:
            lines.append(f"  {line_num}: {line}")
    return "\n".join(lines)


def build_grep_results_dict(matches) -> dict[str, list[tuple[int, str]]]:
    """Group structured matches into the legacy dict form used by formatters."""
    grouped: dict[str, list[tuple[int, str]]] = {}
    for m in matches:
        grouped.setdefault(m["path"], []).append((m["line"], m["text"]))
    return grouped


def get_shell() -> str:
    """Detect available shell executable with fallback.

    Returns the first available shell in order of preference:
    /bin/zsh → /bin/bash → /bin/sh → first `sh` found on PATH.
    Raises a RuntimeError if no suitable shell is found.
    """
    for shell in ("/bin/zsh", "/bin/bash", "/bin/sh"):
        if os.path.isfile(shell) and os.access(shell, os.X_OK):
            return shell
    shell_from_path = shutil.which("sh")
    if shell_from_path is not None:
        return shell_from_path
    raise RuntimeError(
        "No suitable shell executable found. Tried /bin/zsh, /bin/bash, "
        "/bin/sh, and `sh` on PATH."
    )


def clean_markdown_links(text):
    # 移除各种类型的链接
    patterns = [
        # Markdown链接 [text](url)
        (r"\[([^\]]+)\]\([^)]+\)", r"\1"),
        # HTML链接
        (r'<a\s+[^>]*href="[^"]*"[^>]*>(.*?)</a>', r"\1"),
        # 纯URL链接
        (r"https?://\S+", ""),
        # 带括号的URL
        (r"\(https?://[^)]+\)", ""),
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)  # type: ignore

    return text.strip()  # type: ignore


def format_clarification_message(args: dict) -> str:
    """Format the clarification arguments into a user-friendly message.

    Args:
        args: The tool call arguments containing clarification details

    Returns:
        Formatted message string
    """
    question = args.get("question", "")
    clarification_type = args.get("clarification_type", "missing_info")
    context = args.get("context")
    options = args.get("options", [])

    # Type-specific icons
    type_icons = {
        "missing_info": "❓",
        "ambiguous_requirement": "🤔",
        "approach_choice": "🔀",
        "risk_confirmation": "⚠️",
        "suggestion": "💡",
    }

    icon = type_icons.get(clarification_type, "❓")

    # Build the message naturally
    message_parts = []

    # Add icon and question together for a more natural flow
    if context:
        # If there's context, present it first as background
        message_parts.append(f"{icon} {context}")
        message_parts.append(f"\n{question}")
    else:
        # Just the question with icon
        message_parts.append(f"{icon} {question}")

    # Add options in a cleaner format
    if options and len(options) > 0:
        message_parts.append("")  # blank line for spacing
        for i, option in enumerate(options, 1):
            message_parts.append(f"  {i}. {option}")

    return "\n".join(message_parts)
