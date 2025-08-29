# -*- coding: utf-8 -*-
# @Time   : 2025/05/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os
import sys

sys.path.append("..")
import uvicorn

from nova.main import app

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    os.environ["CONFIG_PATH"] = "../config.yaml"
    logger.info("🚀Starting Nova Agent API Server🚀")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=2021,
        reload=False,
        log_level="info",
    )
