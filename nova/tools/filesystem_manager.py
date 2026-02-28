# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Sequence

import wcmatch.glob as wcglob
from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from nova.utils.common import (
    format_content_with_line_numbers,
    perform_string_replacement,
)

LIST_FILES_TOOL_DESCRIPTION = """Lists all files in the filesystem, filtering by directory.

Usage:
- The path parameter must be an absolute path, not a relative path
- The list_files tool will return a list of all files in the specified directory.
- This is very useful for exploring the file system and finding the right file to read or edit.
- You should almost ALWAYS use this tool before using the Read or Edit tools."""

READ_FILE_TOOL_DESCRIPTION = """Reads a file from the filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 500 lines starting from the beginning of the file
- **IMPORTANT for large files and codebase exploration**: Use pagination with offset and limit parameters to avoid context overflow
  - First scan: read_file(path, limit=100) to see file structure
  - Read more sections: read_file(path, offset=100, limit=200) for next 200 lines
  - Only omit limit (read full file) when necessary for editing
- Specify offset and limit: read_file(path, offset=0, limit=100) reads first 100 lines
- Any lines longer than 2000 characters will be truncated
- Results are returned using cat -n format, with line numbers starting at 1
- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.
- You should ALWAYS make sure a file has been read before editing it."""

EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance."""


WRITE_FILE_TOOL_DESCRIPTION = """Writes to a new file in the filesystem.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- The content parameter must be a string
- The write_file tool will create the a new file.
- Prefer to edit existing files over creating new ones when possible."""


GLOB_TOOL_DESCRIPTION = """Find files matching a glob pattern.

Usage:
- The glob tool finds files by matching patterns with wildcards
- Supports standard glob patterns: `*` (any characters), `**` (any directories), `?` (single character)
- Patterns can be absolute (starting with `/`) or relative
- Returns a list of absolute file paths that match the pattern

Examples:
- `**/*.py` - Find all Python files
- `*.txt` - Find all text files in root
- `/subdir/**/*.md` - Find all markdown files under /subdir"""

GREP_TOOL_DESCRIPTION = """Search for a pattern in files.

Usage:
- The grep tool searches for text patterns across files
- The pattern parameter is the text to search for (literal string, not regex)
- The path parameter filters which directory to search in (default is the current working directory)
- The glob parameter accepts a glob pattern to filter which files to search (e.g., `*.py`)
- The output_mode parameter controls the output format:
  - `files_with_matches`: List only file paths containing matches (default)
  - `content`: Show matching lines with file path and line numbers
  - `count`: Show count of matches per file

Examples:
- Search all files: `grep(pattern="TODO")`
- Search Python files only: `grep(pattern="import", glob="*.py")`
- Show matching lines: `grep(pattern="error", output_mode="content")`"""

EXECUTE_TOOL_DESCRIPTION = """Executes a given command in the sandbox environment with proper handling and security measures.

Before executing the command, please follow these steps:

1. Directory Verification:
   - If the command will create new directories or files, first use the ls tool to verify the parent directory exists and is the correct location
   - For example, before running "mkdir foo/bar", first use ls to check that "foo" exists and is the intended parent directory

2. Command Execution:
   - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
   - Examples of proper quoting:
     - cd "/Users/name/My Documents" (correct)
     - cd /Users/name/My Documents (incorrect - will fail)
     - python "/path/with spaces/script.py" (correct)
     - python /path/with spaces/script.py (incorrect - will fail)
   - After ensuring proper quoting, execute the command
   - Capture the output of the command

Usage notes:
  - The command parameter is required
  - Commands run in an isolated sandbox environment
  - Returns combined stdout/stderr output with exit code
  - If the output is very large, it may be truncated
  - VERY IMPORTANT: You MUST avoid using search commands like find and grep. Instead use the grep, glob tools to search. You MUST avoid read tools like cat, head, tail, and use read_file to read files.
  - When issuing multiple commands, use the ';' or '&&' operator to separate them. DO NOT use newlines (newlines are ok in quoted strings)
    - Use '&&' when commands depend on each other (e.g., "mkdir dir && cd dir")
    - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail
  - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of cd

Examples:
  Good examples:
    - execute(command="pytest /foo/bar/tests")
    - execute(command="python /path/to/script.py")
    - execute(command="npm install && npm test")

  Bad examples (avoid these):
    - execute(command="cd /foo/bar && pytest tests")  # Use absolute path instead
    - execute(command="cat file.txt")  # Use read_file tool instead
    - execute(command="find . -name '*.py'")  # Use glob tool instead
    - execute(command="grep -r 'pattern' .")  # Use grep tool instead

Note: This tool is only available if the backend supports execution (SandboxBackendProtocol).
If execution is not supported, the tool will return an error message."""

FILESYSTEM_SYSTEM_PROMPT = """## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`

You have access to a filesystem which you can interact with using these tools.
All file paths must start with a /.

- ls: list files in a directory (requires absolute path)
- read_file: read a file from the filesystem
- write_file: write to a file in the filesystem
- edit_file: edit a file in the filesystem
- glob: find files matching a pattern (e.g., "**/*.py")
- grep: search for text within files"""

EXECUTION_SYSTEM_PROMPT = """## Execute Tool `execute`

You have access to an `execute` tool for running shell commands in a sandboxed environment.
Use this tool to run commands, scripts, tests, builds, and other shell operations.

- execute: run a shell command in the sandbox (returns output and exit code)"""

TOOL_RESULT_TOKEN_LIMIT = 20000  # Same threshold as eviction
TRUNCATION_GUIDANCE = (
    "... [results truncated, try being more specific with your parameters]"
)
DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 500
MAX_FILE_SIZE_MB = 10


def _validate_path(path: str, *, allowed_prefixes: Sequence[str] | None = None) -> str:
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
        msg = f"Path traversal not allowed: {path}"
        raise ValueError(msg)

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


def truncate_if_too_long(result: list[str] | str) -> list[str] | str:
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


@tool(description=LIST_FILES_TOOL_DESCRIPTION)
def filesystem_ls_tool(path: str, tool_call_id: Annotated[str, InjectedToolCallId]):
    validated_path = _validate_path(path)
    cwd = Path.cwd()

    # resolve_path
    validated_path = Path(validated_path)
    if not validated_path.is_absolute():
        validated_path = (cwd / validated_path).resolve()
    if not validated_path.exists() or not validated_path.is_dir():
        return ToolMessage(f"Error: File '{path}' not found", tool_call_id=tool_call_id)

    results: list = []

    cwd_str = str(cwd)
    if not cwd_str.endswith("/"):
        cwd_str += "/"

    # List only direct children (non-recursive)
    try:
        for child_path in validated_path.iterdir():
            try:
                is_file = child_path.is_file()
                is_dir = child_path.is_dir()
            except OSError:
                continue

            abs_path = str(child_path)

            # Non-virtual mode: use absolute paths
            if is_file:
                try:
                    st = child_path.stat()
                    results.append(
                        {
                            "path": abs_path,
                            "is_dir": False,
                            "size": int(st.st_size),
                            "modified_at": datetime.fromtimestamp(
                                st.st_mtime
                            ).isoformat(),
                        }
                    )
                except OSError:
                    results.append({"path": abs_path, "is_dir": False})
            elif is_dir:
                try:
                    st = child_path.stat()
                    results.append(
                        {
                            "path": abs_path + "/",
                            "is_dir": True,
                            "size": 0,
                            "modified_at": datetime.fromtimestamp(
                                st.st_mtime
                            ).isoformat(),
                        }
                    )
                except OSError:
                    results.append({"path": abs_path + "/", "is_dir": True})

    except (OSError, PermissionError) as e:
        return ToolMessage(f"Error ls dir '{path}': {e}", tool_call_id=tool_call_id)

    # Keep deterministic order by path
    results.sort(key=lambda x: x.get("path", ""))

    result = [fi.get("path", "") for fi in results]
    result = truncate_if_too_long(result)
    return ToolMessage(str(result), tool_call_id=tool_call_id)


@tool(description=READ_FILE_TOOL_DESCRIPTION)
def filesystem_read_file_tool(
    file_path: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    offset: int = DEFAULT_READ_OFFSET,
    limit: int = DEFAULT_READ_LIMIT,
):
    validated_path = _validate_path(file_path)
    cwd = Path.cwd()

    validated_path = Path(validated_path)

    # resolve_path
    if not validated_path.is_absolute():
        validated_path = (cwd / validated_path).resolve()
    if not validated_path.exists() or not validated_path.is_file():
        return ToolMessage(
            f"Error: File '{file_path}' not found", tool_call_id=tool_call_id
        )

    try:
        # Open with O_NOFOLLOW where available to avoid symlink traversal
        fd = os.open(validated_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            content = f.read()
        if not content or content.strip() == "":
            return ToolMessage(
                "System reminder: File exists but has empty contents",
                tool_call_id=tool_call_id,
            )

        lines = content.splitlines()
        start_idx = offset
        end_idx = min(start_idx + limit, len(lines))

        if start_idx >= len(lines):
            return ToolMessage(
                f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)",
                tool_call_id=tool_call_id,
            )
        selected_lines = lines[start_idx:end_idx]
        return ToolMessage(
            format_content_with_line_numbers(selected_lines, start_line=start_idx + 1),
            tool_call_id=tool_call_id,
        )

    except (OSError, PermissionError) as e:
        return ToolMessage(
            f"Error reading file '{file_path}': {e}", tool_call_id=tool_call_id
        )


@tool(description=WRITE_FILE_TOOL_DESCRIPTION)
def filesystem_write_file_tool(
    file_path: str, content: str, tool_call_id: Annotated[str, InjectedToolCallId]
):
    validated_path = _validate_path(file_path)
    cwd = Path.cwd()

    validated_path = Path(validated_path)

    # resolve_path
    if not validated_path.is_absolute():
        validated_path = (cwd / validated_path).resolve()

    if validated_path.exists():
        return ToolMessage(
            f"Cannot write to {file_path} because it already exists. Read and then make an edit, or write to a new path.",
            tool_call_id=tool_call_id,
        )
    try:
        # Create parent directories if needed
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        # Prefer O_NOFOLLOW to avoid writing through symlinks
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(validated_path, flags, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)

        return ToolMessage(
            f"Updated file {validated_path}",
            tool_call_id=tool_call_id,
        )

    except (OSError, UnicodeEncodeError) as e:
        return ToolMessage(
            f"Error writing file '{file_path}': {e}",
            tool_call_id=tool_call_id,
        )


@tool(description=EDIT_FILE_TOOL_DESCRIPTION)
def filesystem_edit_file_tool(
    file_path: str,
    old_string: str,
    new_string: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    replace_all: bool = False,
):
    validated_path = _validate_path(file_path)
    cwd = Path.cwd()

    validated_path = Path(validated_path)

    # resolve_path
    if not validated_path.is_absolute():
        validated_path = (cwd / validated_path).resolve()

    if not validated_path.exists():
        return ToolMessage(
            f"Error: File '{file_path}' not found",
            tool_call_id=tool_call_id,
        )
    try:
        # Read securely
        fd = os.open(validated_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            content = f.read()
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

        return ToolMessage(
            f"Successfully replaced {int(occurrences)} instance(s) of the string in '{validated_path}'",
            tool_call_id=tool_call_id,
        )

    except (OSError, UnicodeEncodeError) as e:
        return ToolMessage(
            f"Error editing file '{file_path}': {e}",
            tool_call_id=tool_call_id,
        )


@tool(description=GLOB_TOOL_DESCRIPTION)
def filesystem_glob_tool(
    pattern: str, tool_call_id: Annotated[str, InjectedToolCallId], path: str = "/"
):
    if pattern.startswith("/"):
        pattern = pattern.lstrip("/")

    validated_path = _validate_path(path)
    cwd = Path.cwd()

    if path == "/":
        search_path = cwd
    else:
        validated_path = Path(validated_path)
        if not validated_path.is_absolute():
            validated_path = (cwd / validated_path).resolve()
        search_path = validated_path

    if not search_path.exists() or not search_path.is_dir():
        return ToolMessage(f"Error: File '{path}' not found", tool_call_id=tool_call_id)

    results = []
    try:
        # Use recursive globbing to match files in subdirectories as tests expect
        for matched_path in search_path.rglob(pattern):
            try:
                is_file = matched_path.is_file()
            except OSError:
                continue
            if not is_file:
                continue
            abs_path = str(matched_path)
            try:
                st = matched_path.stat()
                results.append(
                    {
                        "path": abs_path,
                        "is_dir": False,
                        "size": int(st.st_size),
                        "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    }
                )
            except OSError:
                results.append({"path": abs_path, "is_dir": False})

    except (OSError, ValueError) as e:
        return ToolMessage(f"Error glob dir '{path}': {e}", tool_call_id=tool_call_id)

    # Keep deterministic order by path
    results.sort(key=lambda x: x.get("path", ""))

    result = [fi.get("path", "") for fi in results]
    result = truncate_if_too_long(result)
    return ToolMessage(str(result), tool_call_id=tool_call_id)


def _ripgrep_search(
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


def _python_search(
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


def _format_grep_results(
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


def _build_grep_results_dict(matches) -> dict[str, list[tuple[int, str]]]:
    """Group structured matches into the legacy dict form used by formatters."""
    grouped: dict[str, list[tuple[int, str]]] = {}
    for m in matches:
        grouped.setdefault(m["path"], []).append((m["line"], m["text"]))
    return grouped


@tool(description=GREP_TOOL_DESCRIPTION)
def filesystem_grep_tool(
    pattern: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    path: str | None = None,
    glob: str | None = None,
    output_mode: Literal[
        "files_with_matches", "content", "count"
    ] = "files_with_matches",
):
    validated_path = _validate_path(path or ".")
    cwd = Path.cwd()

    try:
        re.compile(pattern)
    except re.error as e:
        return ToolMessage(
            f"Invalid regex pattern: {e}",
            tool_call_id=tool_call_id,
        )

    # resolve_path
    validated_path = Path(validated_path)
    if not validated_path.is_absolute():
        validated_path = (cwd / validated_path).resolve()
    if not validated_path.exists():
        return ToolMessage(f"Error: File '{path}' not found", tool_call_id=tool_call_id)

    # Try ripgrep first
    results = _ripgrep_search(pattern, validated_path, glob)
    if results is None:
        results = _python_search(pattern, validated_path, glob)

    matches = []
    for fpath, items in results.items():
        for line_num, line_text in items:
            matches.append({"path": fpath, "line": int(line_num), "text": line_text})

    if not matches:
        return ToolMessage("No matches found", tool_call_id=tool_call_id)

    formatted = _format_grep_results(_build_grep_results_dict(matches), output_mode)
    formatted = truncate_if_too_long(formatted)
    return ToolMessage(str(formatted), tool_call_id=tool_call_id)
