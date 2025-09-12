# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def set_dotenv():
    load_dotenv(str((Path(__file__).parent.parent.parent / ".env").resolve()))

    logger.info("从.env 文件导入环境成功")
