# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import colorlog

# 全局标志，防止重复初始化日志
_LOG_INITIALIZED = False


def set_log(log_dir="./logs"):
    """设置日志配置，防止重复初始化（支持多进程）

    Args:
        log_dir (str, optional): 日志保存目录，如果为None则使用默认路径
    """
    global _LOG_INITIALIZED

    # 如果已经初始化过，直接返回
    if _LOG_INITIALIZED:
        return

    # 使用进程级别的锁文件防止多进程重复初始化
    pid = os.getpid()
    lock_file = Path(tempfile.gettempdir()) / f"le_agent_log_init_{pid}.lock"

    try:
        # 检查当前进程是否已经初始化过
        if lock_file.exists():
            _LOG_INITIALIZED = True
            return

        # 检查root logger是否已有handler
        root_logger = logging.getLogger()
        if root_logger.handlers:
            # 如果已有handler，标记为已初始化并返回
            _LOG_INITIALIZED = True
            lock_file.touch()  # 创建锁文件
            return

        # 配置日志文件保存路径
        log_dir = Path(log_dir)

        # 创建日志目录（如果不存在）
        log_dir.mkdir(parents=True, exist_ok=True)

        # 生成日志文件名（包含当前日期）
        current_date = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"app_{current_date}.log"

        # 配置格式化器
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - [%(levelname)s] - %(module)s.%(funcName)s:%(lineno)d :: %(message)s",
            log_colors={
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )

        # 文件日志不使用颜色
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - [%(levelname)s] - %(module)s.%(funcName)s:%(lineno)d :: %(message)s"
        )

        # 创建控制台处理器
        console_handler = colorlog.StreamHandler(stream=sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)

        # 获取 root logger 并添加处理器
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)

        # 设置 litellm 的日志级别为 WARNING，并阻止消息向上冒泡
        litellm_logger = logging.getLogger("LiteLLM")
        litellm_logger.setLevel(logging.WARNING)
        litellm_logger.propagate = False  # 阻止消息传递给 root logger

        # 设置 httpx 的日志级别为 WARNING，过滤掉 INFO 级别的HTTP请求日志
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)
        httpx_logger.propagate = False  # 阻止消息传递给 root logger

        # 标记为已初始化
        _LOG_INITIALIZED = True
        lock_file.touch()  # 创建锁文件

        logger = logging.getLogger(__name__)
        logger.info(f"日志已经配置成功 (PID: {pid})")
        logger.info(f"日志文件将保存至: {log_file}")

    except Exception as e:
        # 如果初始化失败，至少确保有基本的日志输出
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.warning(f"日志初始化失败，使用基本配置: {e}")
        _LOG_INITIALIZED = True
