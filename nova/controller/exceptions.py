"""
自定义异常类定义
定义应用中的各种异常类型，包含具体的错误代码和详细信息
"""

from typing import Any, Dict, Optional


class NOVAException(Exception):
    """应用基础异常类"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 500,
        additional_info: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.additional_info = additional_info or {}
        super().__init__(self.message)


class LLMValidationError(NOVAException):
    """LLM 中不存在该模型 异常"""

    def __init__(self, message: str, **kwargs):
        error_code = "LLM_VALIDATION_ERROR"
        status_code = 400
        additional_info = {}
        additional_info.update(kwargs)

        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
            additional_info=additional_info,
        )


class ValidationError(NOVAException):
    """数据验证异常"""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        error_code = "VALIDATION_ERROR"
        status_code = 400
        additional_info = {"field": field} if field else {}
        additional_info.update(kwargs)

        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
            additional_info=additional_info,
        )


# 异常处理工具函数
def create_error_response(exception: NOVAException) -> Dict[str, Any]:
    """
    根据异常创建标准错误响应

    Args:
        exception: 异常实例

    Returns:
        Dict: 标准错误响应格式
    """
    return {
        "error": {
            "code": exception.error_code,
            "message": exception.message,
            "status_code": exception.status_code,
            "additional_info": exception.additional_info,
        }
    }
