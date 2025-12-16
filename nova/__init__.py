# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import os

from nova.utils.env_utils import set_dotenv
from nova.utils.log_utils import set_log
from nova.utils.yaml_utils import load_yaml_config

# 第一步取env中的值，里面有一些LLM的
set_dotenv()

# 第二步，取配置项目
config_path = os.environ.get("CONFIG_PATH", "./config.yaml")
print(f"Loading configuration from {config_path}")
CONF = load_yaml_config(config_path)

# 第三步，设置日志样式
set_log(CONF["SYSTEM"]["log_dir"])
