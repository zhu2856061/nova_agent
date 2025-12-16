# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def set_dotenv(env_path_override: Optional[str] = None) -> bool:
    """
    加载 .env 环境变量文件，支持自定义路径覆盖

    优先级：
    1. 函数入参 env_path_override（最高优先级）
    2. 系统环境变量 ENV_PATH
    3. 默认路径（当前文件向上三级目录的 .env 文件）

    Args:
        env_path_override: 自定义 .env 文件路径，优先级高于 ENV_PATH 和默认路径

    Returns:
        bool: 加载成功返回 True，失败返回 False

    Raises:
        无（所有异常捕获并记录日志，保证函数鲁棒性）
    """
    # 1. 确定最终的 .env 文件路径
    try:
        # 默认路径：当前文件向上三级目录的 .env
        default_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        # 优先级：自定义入参 > 系统环境变量 > 默认路径
        final_env_path = (
            env_path_override or os.environ.get("ENV_PATH") or str(default_env_path)
        )
        # 转换为 Path 对象，提升路径处理兼容性
        final_env_path = Path(final_env_path).resolve()

        # 2. 检查文件是否存在
        if not final_env_path.exists():
            logger.warning(f".env 文件不存在：{final_env_path}，跳过环境变量加载")
            return False

        # 3. 检查文件是否为普通文件（避免目录/链接等）
        if not final_env_path.is_file():
            logger.error(f"指定的 .env 路径不是有效文件：{final_env_path}")
            return False

        # 4. 加载环境变量
        load_dotenv(
            dotenv_path=final_env_path, override=False
        )  # override=False 避免覆盖已有系统环境变量
        logger.info(f"成功从 {final_env_path} 加载环境变量")
        return True

    except Exception as e:
        # 捕获所有异常，避免函数崩溃
        logger.error(f"加载 .env 文件失败：{str(e)}", exc_info=True)
        return False
