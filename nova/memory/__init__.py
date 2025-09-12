import os

from nova import CONF

from .sqlite_cache import SQLiteCacheFixed
from .sqlite_memory import SQLiteStoreFixed

######################################################################################
os.makedirs(CONF["SYSTEM"]["cache_dir"], exist_ok=True)
# 全局变量
SQLITECACHE = SQLiteCacheFixed(
    os.path.join(CONF["SYSTEM"]["cache_dir"], "llm_cache.db"),
)
SQLITESTORE = SQLiteStoreFixed(
    os.path.join(CONF["SYSTEM"]["cache_dir"], "memory_store.db")
)

__all__ = ["SQLITECACHE", "SQLITESTORE"]
