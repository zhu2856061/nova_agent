# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import os

from nova import CONF

from .sqlite_cache import SQLiteCacheFixed
from .sqlite_memory import SQLiteStoreFixed

# 全局变量
SQLITECACHE = SQLiteCacheFixed(os.path.join(CONF.SYSTEM.cache_dir, "llm_cache.db"))
SQLITESTORE = SQLiteStoreFixed(os.path.join(CONF.SYSTEM.cache_dir, "memory_store.db"))
