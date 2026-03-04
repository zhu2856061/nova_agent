# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Annotated, List, Literal

from langchain.tools import InjectedToolCallId, ToolRuntime, tool

from nova.controller.sandbox_exceptions import (
    SandboxError,
    SandboxNotFoundError,
    SandboxRuntimeError,
)
from nova.model.agent import Context, State, Todo
from nova.sandbox.sandbox import Sandbox
from nova.sandbox.sandbox_provider import get_sandbox_provider


# ======================================================================================
# 通用函数
def ensure_sandbox_initialized(
    runtime: ToolRuntime[Context, State] | None = None,
) -> Sandbox:
    """Ensure sandbox is initialized, acquiring lazily if needed.

    On first call, acquires a sandbox from the provider and stores it in runtime state.
    Subsequent calls return the existing sandbox.

    Thread-safety is guaranteed by the provider's internal locking mechanism.

    Args:
        runtime: Tool runtime containing state and context.

    Returns:
        Initialized sandbox instance.

    Raises:
        SandboxRuntimeError: If runtime is not available or thread_id is missing.
        SandboxNotFoundError: If sandbox acquisition fails.
    """
    if runtime is None:
        raise SandboxRuntimeError("Tool runtime not available")

    if runtime.state is None:
        raise SandboxRuntimeError("Tool runtime state not available")

    # Check if sandbox already exists in state
    sandbox_id = runtime.state.sandbox_id
    if sandbox_id is not None:
        sandbox = get_sandbox_provider().get(sandbox_id)

        if sandbox is not None:
            return sandbox
            # Sandbox was released, fall through to acquire new one

    # Lazy acquisition: get thread_id and acquire sandbox
    thread_id = runtime.context.thread_id
    if thread_id is None:
        raise SandboxRuntimeError("Thread ID not available in runtime context")

    provider = get_sandbox_provider()

    print(f"Lazy acquiring sandbox for thread {thread_id}")
    sandbox_id = provider.acquire(thread_id)

    # Update runtime state - this persists across tool calls
    runtime.state.sandbox_id = sandbox_id

    # Retrieve and return the sandbox
    sandbox = provider.get(sandbox_id)
    if sandbox is None:
        raise SandboxNotFoundError(
            "Sandbox not found after acquisition", sandbox_id=sandbox_id
        )

    return sandbox


# builtin tools
# ======================================================================================
# 网络搜索
WEB_SEARCH_TOOL_DESCRIPTION = """A search engine optimized for comprehensive, accurate, and trusted results.
Usage:
- The query parameter is the search query

Examples:
- Search for "Python" on the web: `web_search(query="Python")`
"""


@tool("web_search", description=WEB_SEARCH_TOOL_DESCRIPTION)
async def sandbox_web_search_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    query: List[str],
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.web_search(query)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error listing directory: {type(e).__name__}: {e}"


# ======================================================================================

# ======================================================================================
# 子任务创建
SUBAGENT_CREATION_DESCRIPTION = """\n"""


@tool("create_subagent", description=SUBAGENT_CREATION_DESCRIPTION)
async def create_subagent_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    description: str,
    prompt: str,
    subagent_type: Literal["general-purpose", "bash"],
    max_turns: int | None = None,
):

    pass


# ======================================================================================
# 询问澄清
ASK_CLARIFICATION_DESCRIPTION = """Ask the user for clarification when you need more information to proceed.

    Use this tool when you encounter situations where you cannot proceed without user input:

    - **Missing information**: Required details not provided (e.g., file paths, URLs, specific requirements)
    - **Ambiguous requirements**: Multiple valid interpretations exist
    - **Approach choices**: Several valid approaches exist and you need user preference
    - **Risky operations**: Destructive actions that need explicit confirmation (e.g., deleting files, modifying production)
    - **Suggestions**: You have a recommendation but want user approval before proceeding

    The execution will be interrupted and the question will be presented to the user.
    Wait for the user's response before continuing.

    When to use ask_clarification:
    - You need information that wasn't provided in the user's request
    - The requirement can be interpreted in multiple ways
    - Multiple valid implementation approaches exist
    - You're about to perform a potentially dangerous operation
    - You have a recommendation but need user approval

    Best practices:
    - Ask ONE clarification at a time for clarity
    - Be specific and clear in your question
    - Don't make assumptions when clarification is needed
    - For risky operations, ALWAYS ask for confirmation
    - After calling this tool, execution will be interrupted automatically

    Args:
        question: The clarification question to ask the user. Be specific and clear.
        clarification_type: The type of clarification needed (missing_info, ambiguous_requirement, approach_choice, risk_confirmation, suggestion).
        context: Optional context explaining why clarification is needed. Helps the user understand the situation.
        options: Optional list of choices (for approach_choice or suggestion types). Present clear options for the user to choose from.
"""


@tool("ask_clarification", description=ASK_CLARIFICATION_DESCRIPTION)
async def ask_clarification_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
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
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.ask_clarification(
            question, clarification_type, context, options
        )
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 read file 操作
READ_FILE_DESCRIPTION = """Reads a file from the filesystem. You can access any file directly by using this tool.
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

DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 500


@tool("read_file", description=READ_FILE_DESCRIPTION)
async def sandbox_read_file_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    file_path: str,
    offset: int = DEFAULT_READ_OFFSET,
    limit: int = DEFAULT_READ_LIMIT,
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.read_file(file_path, offset, limit)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 read file 操作
WRITE_FILE_DESCRIPTION = """Writes to a new file in the filesystem.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- The content parameter must be a string
- The write_file tool will create the a new file.
- Prefer to edit existing files over creating new ones when possible."""


@tool("write_file", description=WRITE_FILE_DESCRIPTION)
async def sandbox_write_file_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    file_path: str,
    content: str,
    append: bool = False,
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.write_file(file_path, content, append)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 edit file 操作
EDIT_FILE_DESCRIPTION = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance."""


@tool("edit_file", description=EDIT_FILE_DESCRIPTION)
async def sandbox_edit_file_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.edit_file(file_path, old_string, new_string, replace_all)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 ls 操作
SANDBOX_LS_DESCRIPTION = """Lists all files in the filesystem, filtering by directory.

Usage:
- The path parameter must be an absolute path, not a relative path
- The ls tool will return a list of all files in the specified directory.
- This is very useful for exploring the file system and finding the right file to read or edit.
- You should almost ALWAYS use this tool before using the read or edit tools."""


@tool("ls", description=SANDBOX_LS_DESCRIPTION)
async def sandbox_ls_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    path: str,
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.ls(path)
        if not result:
            return "(empty)"
        return result
    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 glob 操作
GLOB_DESCRIPTION = """Find files matching a glob pattern.

Usage:
- The glob tool finds files by matching patterns with wildcards
- Supports standard glob patterns: `*` (any characters), `**` (any directories), `?` (single character)
- Patterns can be absolute (starting with `/`) or relative
- Returns a list of absolute file paths that match the pattern

Examples:
- `**/*.py` - Find all Python files
- `*.txt` - Find all text files in root
- `/subdir/**/*.md` - Find all markdown files under /subdir"""


@tool("glob", description=GLOB_DESCRIPTION)
async def sandbox_glob_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    pattern: str,
    path: str = "/",
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.glob(pattern, path)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 glob 操作
GREP_DESCRIPTION = """Search for a pattern in files.

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


@tool("grep", description=GREP_DESCRIPTION)
async def sandbox_grep_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    output_mode: Literal[
        "files_with_matches", "content", "count"
    ] = "files_with_matches",
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.grep(pattern, path, glob, output_mode)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ======================================================================================


# ======================================================================================
# sandbox 中的 execute 操作
EXECUTE_DESCRIPTION = """Executes a given command in the sandbox environment with proper handling and security measures.

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


@tool("execute", description=EXECUTE_DESCRIPTION)
async def sandbox_execute_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    command: str,
):
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.execute(command)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


WRITE_TODOS_TOOL_DESCRIPTION = """Use this tool to create and manage a structured task list for your current work session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.

Only use this tool if you think it will be helpful in staying organized. If the user's request is trivial and takes less than 3 steps, it is better to NOT use this tool and just do the task directly.

## When to Use This Tool
Use this tool in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. The plan may need future revisions or updates based on results from the first few steps

## How to Use This Tool
1. When you start working on a task - Mark it as in_progress BEFORE beginning work.
2. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation.
3. You can also update future tasks, such as deleting them if they are no longer necessary, or adding new tasks that are necessary. Don't change previously completed tasks.
4. You can make several updates to the todo list at once. For example, when you complete a task, you can mark the next task you need to start as in_progress.

## When NOT to Use This Tool
It is important to skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

## Task States and Management

1. **Task States**: Use these states to track progress:
   - pending: Task not yet started
   - in_progress: Currently working on (you can have multiple tasks in_progress at a time if they are not related to each other and can be run in parallel)
   - completed: Task finished successfully

2. **Task Management**:
   - Update task status in real-time as you work
   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
   - Complete current tasks before starting new ones
   - Remove tasks that are no longer relevant from the list entirely
   - IMPORTANT: When you write this todo list, you should mark your first task (or tasks) as in_progress immediately!.
   - IMPORTANT: Unless all tasks are completed, you should always have at least one task in_progress to show the user that you are working on something.

3. **Task Completion Requirements**:
   - ONLY mark a task as completed when you have FULLY accomplished it
   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
   - When blocked, create a new task describing what needs to be resolved
   - Never mark a task as completed if:
     - There are unresolved issues or errors
     - Work is partial or incomplete
     - You encountered blockers that prevent completion
     - You couldn't find necessary resources or dependencies
     - Quality standards haven't been met

4. **Task Breakdown**:
   - Create specific, actionable items
   - Break complex tasks into smaller, manageable steps
   - Use clear, descriptive task names

Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully
Remember: If you only need to make a few tool calls to complete a task, and it is clear what you need to do, it is better to just do the task directly and NOT call this tool at all."""


@tool("write_todos", description=WRITE_TODOS_TOOL_DESCRIPTION)
async def write_todos_tool(
    tool_call_id: Annotated[str, InjectedToolCallId],
    runtime: ToolRuntime[Context, State],
    todos: list[Todo],
) -> str:
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        result = sandbox.todo_list(todos)
        return result

    except SandboxError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


# ===========================
# 数字人核心工具

Digital_Human_Manager = {
    "web_search": sandbox_web_search_tool,
    # "create_subagent": create_subagent_tool,
    "ask_clarification": ask_clarification_tool,
    "read_file": sandbox_read_file_tool,
    "write_file": sandbox_write_file_tool,
    "edit_file": sandbox_edit_file_tool,
    "ls": sandbox_ls_tool,
    "glob": sandbox_glob_tool,
    "grep": sandbox_grep_tool,
    "execute": sandbox_execute_tool,
    "write_todos": write_todos_tool,
}

# ===========================
