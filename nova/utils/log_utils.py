# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import inspect
import logging
import os
import sys
import tempfile
from datetime import datetime
from logging import Formatter, Logger, LogRecord
from pathlib import Path
from typing import Optional, Tuple, Union

import colorlog

# 全局标志，防止重复初始化日志
_LOG_INITIALIZED = False

# ========== 全局 Logger 定义 ==========
logger = logging.getLogger(__name__)


# ========== 自定义格式化器（解决自定义字段缺失问题） ==========
class CustomFormatter(Formatter):
    """自定义格式化器，确保自定义字段存在默认值"""

    def format(self, record: LogRecord) -> str:
        # 为自定义字段设置默认值（优先使用 record 已有值，无则用默认）
        record.caller_module = getattr(
            record, "caller_module", getattr(record, "module", "unknown")
        )
        record.caller_func = getattr(
            record, "caller_func", getattr(record, "funcName", "unknown")
        )
        record.caller_lineno = getattr(
            record, "caller_lineno", getattr(record, "lineno", 0)
        )
        # 确保行号是整数（最终防护）
        if not isinstance(record.caller_lineno, int):  # type: ignore
            record.caller_lineno = (
                int(record.caller_lineno) if str(record.caller_lineno).isdigit() else 0  # type: ignore
            )
        return super().format(record)


class CustomColoredFormatter(colorlog.ColoredFormatter):
    """带颜色的自定义格式化器，兼容自定义字段"""

    def format(self, record: LogRecord) -> str:
        # 为自定义字段设置默认值
        record.caller_module = getattr(
            record, "caller_module", getattr(record, "module", "unknown")
        )
        record.caller_func = getattr(
            record, "caller_func", getattr(record, "funcName", "unknown")
        )
        record.caller_lineno = getattr(
            record, "caller_lineno", getattr(record, "lineno", 0)
        )
        # 确保行号是整数
        if not isinstance(record.caller_lineno, int):  # type: ignore
            record.caller_lineno = (
                int(record.caller_lineno) if str(record.caller_lineno).isdigit() else 0  # type: ignore
            )
        return super().format(record)


# ========== 自定义日志记录器（简化，仅保留必要功能） ==========
class CallerAwareLogger(Logger):
    def makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: str,
        args: tuple,
        exc_info: Optional[Union[Exception, Tuple[Exception, ...]]],
        func: Optional[str] = None,
        extra: Optional[dict] = None,
        sinfo: Optional[str] = None,
    ) -> LogRecord:
        """重写 makeRecord，注入自定义字段（确保类型正确）"""
        record = super().makeRecord(
            name,
            level,
            fn,
            lno,
            msg,
            args,
            exc_info,  # type: ignore
            func,
            extra,
            sinfo,
        )
        # 从 extra 中提取自定义字段（如有）
        if extra:
            setattr(record, "caller_module", extra.get("caller_module", ""))
            setattr(record, "caller_func", extra.get("caller_func", ""))
            setattr(record, "caller_lineno", int(extra.get("caller_lineno", 0)))
        return record


def set_log(log_dir: str = "./logs") -> None:
    """设置日志配置，防止重复初始化（支持多进程、自定义调用方字段）"""
    global _LOG_INITIALIZED
    global logger

    if _LOG_INITIALIZED:
        return

    # 进程级锁防止多进程重复初始化
    pid = os.getpid()
    lock_file = Path(tempfile.gettempdir()) / f"le_agent_log_init_{pid}.lock"

    try:
        if lock_file.exists():
            _LOG_INITIALIZED = True
            return

        root_logger = logging.getLogger()
        if root_logger.handlers:
            _LOG_INITIALIZED = True
            lock_file.touch()
            return

        # 替换默认 Logger 为自定义 Logger
        logging.setLoggerClass(CallerAwareLogger)

        # 配置日志目录和文件
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        current_date = datetime.now().strftime("%Y%m%d")
        log_file = log_dir_path / f"app_{current_date}.log"

        # ========== 关键修复：使用自定义格式化器 ==========
        # 控制台带颜色格式化器
        console_formatter = CustomColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - [%(levelname)s] - "
            "%(caller_module)s.%(caller_func)s:%(caller_lineno)d :: %(message)s",
            log_colors={
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            style="%",
        )

        # 文件无颜色格式化器
        file_formatter = CustomFormatter(
            "%(asctime)s - %(name)s - [%(levelname)s] - "
            "%(caller_module)s.%(caller_func)s:%(caller_lineno)d :: %(message)s",
            style="%",
        )

        # 创建处理器
        console_handler = colorlog.StreamHandler(stream=sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)

        # 配置 root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)

        # 过滤第三方库日志
        for lib_name in ["LiteLLM", "httpx", "urllib3", "reflex"]:
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.WARNING)
            lib_logger.propagate = False

        # 重新获取配置后的 logger
        logger = logging.getLogger(__name__)
        _LOG_INITIALIZED = True
        lock_file.touch()

        logger.info(f"日志配置成功 (PID: {pid})")
        logger.info(f"日志文件路径: {log_file.resolve()}")

    except Exception as e:
        # 降级为基础配置
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - [%(levelname)s] - %(module)s.%(funcName)s:%(lineno)d :: %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        logger = logging.getLogger(__name__)
        logger.warning(f"日志初始化失败，使用基础配置: {str(e)}")
        _LOG_INITIALIZED = True


def _get_caller_info() -> Tuple[str, str, int]:
    """获取调用方的模块名、函数名、行号（确保行号为整数）"""
    try:
        # stack[0]: _get_caller_info, stack[1]: 日志封装函数, stack[2]: 调用方
        stack = inspect.stack()[2]
        frame = stack[0]
        # 模块名（去掉路径和后缀）
        caller_module = Path(frame.f_code.co_filename).stem
        # 函数名
        caller_func = frame.f_code.co_name or "unknown"
        # 行号（强制转换为整数）
        caller_lineno = int(stack[2])
        return caller_module, caller_func, caller_lineno
    except IndexError:
        # 栈帧不足（如直接在模块顶级调用）
        return "unknown", "unknown", 0
    except Exception as e:
        logger.error(f"获取调用方信息失败: {str(e)}")
        return "unknown", "unknown", 0
    finally:
        # 清理栈帧引用，避免内存泄漏
        try:
            del stack
        except Exception:
            pass


def set_color(log: str, color: str = "red", highlight: bool = True) -> str:
    """终端日志着色（兼容非终端输出）"""
    color_map = {
        "black": 0,
        "red": 1,
        "green": 2,
        "yellow": 3,
        "blue": 4,
        "pink": 5,
        "cyan": 6,
        "white": 7,
    }
    # 非终端输出（文件/管道）直接返回原日志
    if not sys.stdout.isatty():
        return log
    color_code = color_map.get(color.lower(), 7)
    mode = "1" if highlight else "0"
    return f"\033[{mode};3{color_code}m{log}\033[0m"


def log_info_set_color(trace_id: str, node: str, message, color: str = "pink"):
    """带颜色的信息日志，显示调用方位置"""
    if not _LOG_INITIALIZED:
        set_log()
    caller_module, caller_func, caller_lineno = _get_caller_info()
    log_msg = f"trace_id={trace_id} | node={node} | message={message}"
    logger.info(
        set_color(log_msg, color),
        extra={
            "caller_module": caller_module,
            "caller_func": caller_func,
            "caller_lineno": caller_lineno,
        },
    )


def log_error_set_color(trace_id: str, node: str, e, color: str = "red") -> str:
    """带颜色的错误日志，显示调用方位置并返回错误信息"""
    if not _LOG_INITIALIZED:
        set_log()
    caller_module, caller_func, caller_lineno = _get_caller_info()
    # 处理异常信息
    if isinstance(e, Exception):
        err_detail = f"{type(e).__name__}: {str(e)}"
        exc_info = e
    else:
        err_detail = str(e)
        exc_info = None
    log_msg = f"trace_id={trace_id} | node={node} | error={err_detail}"
    # 记录日志（包含异常堆栈）
    logger.error(
        set_color(log_msg, color),
        extra={
            "caller_module": caller_module,
            "caller_func": caller_func,
            "caller_lineno": caller_lineno,
        },
        exc_info=exc_info,
    )
    return log_msg
