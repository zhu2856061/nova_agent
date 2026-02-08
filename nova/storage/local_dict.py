# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class InDictStore:
    """独立字典存储

    write(self, key: str, contents: str) 基于key 写入内容
    read(self, key: str) 基于key 读取内容
    list(self, key: str) 基于key 列出内容
    delete(self, key: str) 基于key 删除内容
    """

    def __init__(self) -> None:
        self.storage = {}

    def write(self, key: str, contents: str) -> None:
        if isinstance(contents, bytes):
            contents = contents.decode("utf-8")
        self.storage[key] = contents

    def read(self, key: str) -> str:
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    def list(self, key: str) -> list[str]:
        files = []
        for file in self.storage:
            if not file.startswith(key):
                continue
            suffix = file.removeprefix(key)
            parts = suffix.split("/")
            if parts[0] == "":
                parts.pop(0)
            if len(parts) == 1:
                files.append(file)
            else:
                dir_path = os.path.join(key, parts[0])
                if not dir_path.endswith("/"):
                    dir_path += "/"
                if dir_path not in files:
                    files.append(dir_path)
        return files

    def delete(self, key: str) -> None:
        try:
            keys_to_delete = [key for key in self.storage.keys() if key.startswith(key)]
            for key in keys_to_delete:
                del self.storage[key]
            logger.debug(f"Cleared in-memory file store: {key}")
        except Exception as e:
            logger.error(f"Error clearing in-memory file store: {str(e)}")
