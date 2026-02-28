# -*- coding: utf-8 -*-
# @Time   : 2026/02/06
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NotRequired

from typing_extensions import TypedDict


class FileInfo(TypedDict):
    """Structured file listing info.

    Minimal contract used across backends. Only "path" is required.
    Other fields are best-effort and may be absent depending on backend.
    """

    path: str
    is_dir: NotRequired[bool]
    size: NotRequired[int]  # bytes (approx)
    modified_at: NotRequired[str]  # ISO timestamp if known


@dataclass
class WriteResult:
    """Result from backend write operations.

    Attributes:
        error: Error message on failure, None on success.
        path: Absolute path of written file, None on failure.
        files_update: State update dict for checkpoint backends, None for external storage.
            Checkpoint backends populate this with {file_path: file_data} for LangGraph state.
            External backends set None (already persisted to disk/S3/database/etc).

    Examples:
        >>> # Checkpoint storage
        >>> WriteResult(path="/f.txt", files_update={"/f.txt": {...}})
        >>> # External storage
        >>> WriteResult(path="/f.txt", files_update=None)
        >>> # Error
        >>> WriteResult(error="File exists")
    """

    error: str | None = None
    path: str | None = None
    files_update: dict[str, Any] | None = None


@dataclass
class EditResult:
    """Result from backend edit operations.

    Attributes:
        error: Error message on failure, None on success.
        path: Absolute path of edited file, None on failure.
        files_update: State update dict for checkpoint backends, None for external storage.
            Checkpoint backends populate this with {file_path: file_data} for LangGraph state.
            External backends set None (already persisted to disk/S3/database/etc).
        occurrences: Number of replacements made, None on failure.

    Examples:
        >>> # Checkpoint storage
        >>> EditResult(path="/f.txt", files_update={"/f.txt": {...}}, occurrences=1)
        >>> # External storage
        >>> EditResult(path="/f.txt", files_update=None, occurrences=2)
        >>> # Error
        >>> EditResult(error="File not found")
    """

    error: str | None = None
    path: str | None = None
    files_update: dict[str, Any] | None = None
    occurrences: int | None = None
