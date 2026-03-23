# -*- coding: utf-8 -*-
# @Time   : 2026/03/02 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

"""
自定义异常类定义
定义应用中的各种异常类型，包含具体的错误代码和详细信息
"""


class LLMValidationError(Exception):
    """LLM 中不存在该模型 异常"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = "LLM_VALIDATION_ERROR"
        self.status_code = 400

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"[status_code={self.status_code}]->[error_code={self.error_code}]{self.message} ({detail_str})"
        return self.message


class LLMContextExceededError(Exception):
    """LLM 中不存在该模型 异常"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = "LLM_ContextExceeded_ERROR"
        self.status_code = 401

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"[status_code={self.status_code}]->[error_code={self.error_code}]{self.message} ({detail_str})"
        return self.message


class LLMBadRequestError(Exception):
    """LLM 中不存在该模型 异常"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = "LLM_BadRequest_ERROR"
        self.status_code = 402

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"[status_code={self.status_code}]->[error_code={self.error_code}]{self.message} ({detail_str})"
        return self.message


class LLMExceptionError(Exception):
    """LLM 中不存在该模型 异常"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = "LLM_Exception_ERROR"
        self.status_code = 403

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"[status_code={self.status_code}]->[error_code={self.error_code}]{self.message} ({detail_str})"
        return self.message
