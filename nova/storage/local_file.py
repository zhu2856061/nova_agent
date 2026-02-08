# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)


class LocalFileStore:
    """独立文件存储

    write(self, path: str, contents: str | bytes) 向指定路径文件写入内容

    read(self, path: str) 读取指定路径文件内容

    list(self, path: str) 列出指定路径下的文件和目录

    delete(self, path: str) 删除指定路径的文件或目录
    """

    def __init__(self, root: str):
        if root.startswith("~"):
            root = os.path.expanduser(root)
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def _get_full_path(self, path: str) -> str:
        if path.startswith("/"):
            path = path[1:]
        return os.path.join(self.root, path)

    def write(self, path: str, contents: str | bytes) -> None:
        full_path = self._get_full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        mode = "w" if isinstance(contents, str) else "wb"
        with open(full_path, mode) as f:
            f.write(contents)

    def read(self, path: str) -> str:
        full_path = self._get_full_path(path)
        with open(full_path, "r") as f:
            return f.read()

    def list(self, path: str) -> list[str]:
        full_path = self._get_full_path(path)
        files = [os.path.join(path, f) for f in os.listdir(full_path)]
        files = [f + "/" if os.path.isdir(self._get_full_path(f)) else f for f in files]
        return files

    def delete(self, path: str) -> None:
        try:
            full_path = self._get_full_path(path)
            if not os.path.exists(full_path):
                logger.debug(f"Local path does not exist: {full_path}")
                return
            if os.path.isfile(full_path):
                os.remove(full_path)
                logger.debug(f"Removed local file: {full_path}")
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                logger.debug(f"Removed local directory: {full_path}")
        except Exception as e:
            logger.error(f"Error clearing local file store: {str(e)}")
