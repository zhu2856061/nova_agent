# -*- coding: utf-8 -*-
# @Time   : 2025/05/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import os

import uvicorn

logger = logging.getLogger(__name__)

os.environ["CONFIG_PATH"] = "../config.yaml"

if __name__ == "__main__":
    logger.info("🚀Starting Nova Agent API Server🚀")
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=2021,
        reload=False,
        log_level="info",
    )
