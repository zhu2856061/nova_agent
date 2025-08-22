# -*- coding: utf-8 -*-
# @Time   : 2025/04/03 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import gzip
import logging
import logging.handlers
import os
import shutil
from typing import Any, Dict

import yaml


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """Load and process YAML configuration file."""
    # 如果文件不存在，返回{}
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Config file '{file_path}' not found.")

    with open(file_path, "r") as f:
        config = yaml.safe_load(f)

    return config


# gunicorn.conf.py
config_path = os.getenv("CONFIG_PATH", "config.yaml")
CONF = load_yaml_config(config_path)

# 绑定地址和端口
bind = CONF["SYSTEM"]["IP_PORT"]

# Worker 数量
workers = CONF["SYSTEM"]["WORKERS"]  # 根据你的 CPU 核心数调整

# 超时设置
timeout = CONF["SYSTEM"]["TIMEOUT"]  # 请求超时时间（秒）


logging.info(f"bind: {bind}, workers: {workers}, timeout: {timeout}")

if bind is None:
    raise Exception("请设置环境变量 IP_PORT")

# Worker 类型
worker_class = "uvicorn.workers.UvicornWorker"

# 日志级别
loglevel = "info"

# 使用外部日志配置文件
logconfig = "gunicorn_deploy/logging.conf"


# 自定义日志处理器
class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}.gz"
                dfn = f"{self.baseFilename}.{i + 1}.gz"
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = f"{self.baseFilename}.1"
            if os.path.exists(self.baseFilename):
                with open(self.baseFilename, "rb") as f_in:
                    with gzip.open(dfn + ".gz", "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(self.baseFilename)
        self.stream = self._open()


# 确保日志目录存在
log_dir = "./logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)
