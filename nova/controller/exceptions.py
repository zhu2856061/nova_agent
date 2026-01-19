"""
自定义异常类定义
定义应用中的各种异常类型，包含具体的错误代码和详细信息
"""

from typing import Any, Dict, Optional


class NOVAException(Exception):
    """AI客服机器人应用基础异常类"""

    def __init__(
        self,
        error_code: str,
        detail: str,
        status_code: int = 500,
        additional_info: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        self.additional_info = additional_info or {}
        super().__init__(self.detail)


class ValidationError(NOVAException):
    """数据验证异常"""

    def __init__(self, detail: str, field: Optional[str] = None, **kwargs):
        error_code = "VALIDATION_ERROR"
        status_code = 400
        additional_info = {"field": field} if field else {}
        additional_info.update(kwargs)

        super().__init__(
            error_code=error_code,
            detail=detail,
            status_code=status_code,
            additional_info=additional_info,
        )


class ExternalContextError(NOVAException):
    """外部上下文格式异常"""

    def __init__(self, detail: str, context_data: Optional[Any] = None, **kwargs):
        error_code = "EXTERNAL_CONTEXT_ERROR"
        status_code = 401
        additional_info = {"context_data": context_data} if context_data else {}
        additional_info.update(kwargs)

        super().__init__(
            error_code=error_code,
            detail=detail,
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
            "message": exception.detail,
            "status_code": exception.status_code,
            "additional_info": exception.additional_info,
        }
    }
