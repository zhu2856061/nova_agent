# -*- coding: utf-8 -*-
# @Time   : 2026/02/08
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import os

from nova.model.config import AppConfig

# 第一步取env中的值，里面有一些LLM的
AppConfig.set_dotenv()

# 第二步，取配置项目
config_path = os.environ.get("CONFIG_PATH", "./config.yaml")
print(f"Loading configuration from {config_path}")
CONF = AppConfig.from_yaml(config_path)

# 第三步，设置日志样式
CONF.set_log()
