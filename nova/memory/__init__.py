# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .sqlite_cache import SQLiteCacheFixed
from .sqlite_memory import SQLiteStoreFixed

SQLITECACHE = None
SQLITESTORE = None

if CONF:
    SQLITECACHE = SQLiteCacheFixed(CONF.SYSTEM.cache_dir)
    SQLITESTORE = SQLiteStoreFixed(CONF.SYSTEM.cache_dir)
