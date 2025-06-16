# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import sys

import colorlog


def set_log():
    # 配置基本日志 (可以先不包含 format，或者包含你想要的默认 format)
    # logging.basicConfig(level=logging.INFO)
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - [%(levelname)8s] - %(module)s.%(funcName)s:%(lineno)d :: %(message)s",
        log_colors={
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
    # 创建一个处理其他目录下日志的 handler
    info_handler = colorlog.StreamHandler(stream=sys.stdout)
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO)
    info_filter = logging.Filter()  # 默认处理所有 logger
    info_handler.addFilter(info_filter)

    # 获取 root logger 并添加 handler
    root_logger = logging.getLogger()
    root_logger.addHandler(info_handler)
    root_logger.setLevel(logging.INFO)

    # 设置 litellm 的日志级别为 WARNING，并阻止消息向上冒泡
    litellm_logger = logging.getLogger("LiteLLM")
    litellm_logger.setLevel(logging.WARNING)
    litellm_logger.propagate = False  # 阻止消息传递给 root logger

    logger = logging.getLogger(__name__)
    logger.info("日志已经配置成功")
