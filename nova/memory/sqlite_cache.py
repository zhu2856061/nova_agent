# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import os
import zlib
from pathlib import Path, PosixPath
from typing import Any, Optional, Type, Union

import dill
from langchain_core.caches import RETURN_VAL_TYPE, BaseCache
from sqlalchemy import Column, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing_extensions import override

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
"""
source : https://api.python.langchain.com/en/latest/_modules/langchain_community/cache.html#InMemoryCache

This workaround is to solve this: https://github.com/langchain-ai/langchain/issues/22389
Create a caching class that looks like it's just in memory but actually saves to sql

* 采用异步 - aiosqlite

"""
logger = logging.getLogger(__name__)

Base = declarative_base()


class FullLLMCache(Base):  # type: ignore[misc,valid-type]
    """SQLite table for full LLM Cache (all generations)."""

    __tablename__ = "full_llm_cache"
    prompt = Column(String, primary_key=True)
    llm = Column(String, primary_key=True)
    response = Column(String)


class SQLiteCacheFixed(BaseCache):
    """Cache that stores things in memory."""

    def __init__(
        self,
        database_path: Union[str, PosixPath],
        cache_schema: Type[FullLLMCache] = FullLLMCache,
    ) -> None:
        os.makedirs(database_path, exist_ok=True)
        self.database_path = Path(database_path)
        self.cache_schema = cache_schema
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.database_path}", echo=True
        )
        # self.engine = create_engine(f"sqlite:///{database_path}")
        self.async_session = async_sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=AsyncSession
        )
        self._cache = {}
        self.is_async = False
        # Ensure the database and table are created
        try:
            asyncio.run(self._initialize_database())
            asyncio.run(self.aclear())
        except Exception:
            self._init_task = asyncio.create_task(self._initialize_database())
            self._load_cache_task = asyncio.create_task(self.aclear())
            self.is_async = True

    async def _initialize_database(self):
        """Create the database and tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(self.cache_schema.metadata.create_all)

    async def alookup(self, prompt: str, llm_string: str) -> Optional[RETURN_VAL_TYPE]:
        """Look up based on prompt and llm_string."""
        key = (prompt, llm_string)
        if key in self._cache:
            return self._cache[key]

    async def aupdate(
        self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE
    ) -> None:
        """Update based on prompt and llm_string."""
        # 确保初始化完成
        if self.is_async:
            await self._init_task
            await self._load_cache_task

        self._cache[(prompt, llm_string)] = return_val

        async with self.async_session() as session:
            async with session.begin():
                data = zlib.compress(
                    dill.dumps({"key": (prompt, llm_string), "value": return_val})
                )
                item = self.cache_schema(prompt=prompt, llm=llm_string, response=data)
                await session.merge(item)

    async def aclear(self, **kwargs: Any) -> None:
        # 确保初始化完成
        if self.is_async:
            await self._init_task
        """Clear cache."""
        stmt = select(self.cache_schema.response)
        async with self.async_session() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
            if rows:
                try:
                    datas = [dill.loads(zlib.decompress(row[0])) for row in rows]
                    self._cache = {d["key"]: d["value"] for d in datas}
                except Exception:
                    logger.warning(
                        "Retrieving a cache value that could not be deserialized "
                        "properly. This is likely due to the cache being in an "
                        "older format. Please recreate your cache to avoid this "
                        "error."
                    )
                    # In a previous life we stored the raw text directly
                    # in the table, so assume it's in that format.
                    self._cache = {}

    def lookup(self, prompt: str, llm_string: str) -> Optional[RETURN_VAL_TYPE]:
        """Look up based on prompt and llm_string."""
        try:
            # 检查是否已有运行的事件循环
            return asyncio.run(self.alookup(prompt, llm_string))
        except Exception:
            # 没有运行的事件循环，创建新的
            loop = asyncio.get_running_loop()
            # 如果有，使用create_task并等待（适用于Python 3.7+）
            return loop.run_until_complete(self.alookup(prompt, llm_string))

    def update(self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE) -> None:
        """Update cache based on prompt and llm_string."""
        try:
            return asyncio.run(self.aupdate(prompt, llm_string, return_val))
        except Exception:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.aupdate(prompt, llm_string, return_val))

    @override
    def clear(self, **kwargs: Any) -> None:
        """Clear cache."""
        try:
            return asyncio.run(self.aclear(**kwargs))
        except Exception:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.aclear(**kwargs))
