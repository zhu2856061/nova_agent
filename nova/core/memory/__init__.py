import os

from nova.core import CONF

from .sqlite_cache import SQLiteCacheFixed
from .sqlite_memory import SQLiteStore

######################################################################################
os.makedirs(CONF["SYSTEM"]["cache_dir"], exist_ok=True)
# 全局变量
SQLITECACHE = SQLiteCacheFixed(
    os.path.join(CONF["SYSTEM"]["cache_dir"], "llm_cache.db"),
)
SQLITESTORE = SQLiteStore(os.path.join(CONF["SYSTEM"]["cache_dir"], "memory_store.db"))

__all__ = ["SQLITECACHE", "SQLITESTORE"]
