# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def set_dotenv(env_file):
    load_dotenv(env_file)
    logger.info("从.env 文件导入环境成功")
