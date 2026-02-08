# -*- coding: utf-8 -*-
# @Time   : 2025/09/04 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import datetime
import functools
import logging
import os
import zlib
from importlib import util
from pathlib import Path, PosixPath
from typing import Any, Dict, Iterable, List, Tuple, Type, Union

import dill
from langgraph.store.base import (
    BaseStore,
    GetOp,
    IndexConfig,
    Item,
    ListNamespacesOp,
    MatchCondition,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

"""

* 采用异步 - aiosqlite
https://docs.langchain.com/oss/python/langgraph/persistence#replay
"""

logger = logging.getLogger(__name__)

Base = declarative_base()


class KEYVALUESTORE(Base):  # type: ignore[misc,valid-type]
    """SQLite table for key value store."""

    __tablename__ = "key_value_store"
    namespace = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    value = Column(String)  # -- zlib.compress 序列化（需在put/get时序列化/反序列化）
    created_at = Column(DateTime, default=datetime.timezone.utc)
    updated_at = Column(
        DateTime, default=datetime.timezone.utc, onupdate=datetime.timezone.utc
    )


class SQLiteStoreFixed(BaseStore):
    """
    SQLite-backed store with persistent key-value storage and optional vector search.

    核心：
    1. 使用SQLite数据库实现数据持久化
    2. 设计数据表存储键值数据
    3. 保持与InMemoryStore完全兼容的API接口
    """

    def __init__(
        self,
        database_path: Union[str, PosixPath],
        *,
        index: IndexConfig | None = None,
        cache_schema: Type[KEYVALUESTORE] = KEYVALUESTORE,
    ) -> None:
        """
        初始化SQLiteStore

        Args:
            db_path: SQLite数据库文件路径（默认：langchain_store.db）
            index: 向量索引配置（同InMemoryStore）
        """
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
            asyncio.run(self._aclear())
        except Exception:
            self._init_task = asyncio.create_task(self._initialize_database())
            self._load_cache_task = asyncio.create_task(self._aclear())
            self.is_async = True

    async def _initialize_database(self):
        """Create the database and tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(self.cache_schema.metadata.create_all)

    async def wait_initialized(self):
        """等待初始化完成（如果需要确保初始化完成后再操作）"""
        await self._init_task
        await self._load_cache_task

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """批量处理操作（同步版）：同InMemoryStore接口"""
        results, put_ops, search_ops = self._prepare_ops(ops)

        # 处理搜索操作
        if search_ops:
            query_embeddings = None
            self._batch_search(search_ops, query_embeddings, results)

        await self._apply_put_ops(put_ops)

        return results

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        return asyncio.run(self.abatch(ops))

    def _filter_items(self, op: SearchOp) -> list[tuple[Item, list[list[float]]]]:
        """Filter items by namespace and filter function, return items with their embeddings."""
        namespace_prefix = op.namespace_prefix

        def filter_func(item: Item) -> bool:
            if not op.filter:
                return True

            return all(
                _compare_values(item.value.get(key), filter_value)
                for key, filter_value in op.filter.items()
            )

        filtered = []
        for namespace in self._cache:
            if not (
                namespace[: len(namespace_prefix)] == namespace_prefix
                if len(namespace) >= len(namespace_prefix)
                else False
            ):
                continue

            for key, item in self._cache[namespace].items():
                if filter_func(item):
                    filtered.append((item, []))

        return filtered

    # ------------------------------
    # 核心工具函数（重写SQLite适配逻辑）
    # ------------------------------
    async def _apply_put_ops(
        self, put_ops: Dict[Tuple[Tuple[str, ...], str], PutOp]
    ) -> None:
        """
        应用写入操作到SQLite（替代内存字典更新）
        支持新增/更新/删除（value为None时删除）
        """
        # 确保初始化完成
        if self.is_async:
            await self._init_task
            await self._load_cache_task

        current_time = datetime.datetime.now(datetime.timezone.utc)

        for (namespace, key), op in put_ops.items():
            if namespace not in self._cache:
                self._cache[namespace] = {}

            if op.value is None:
                self._cache[namespace].pop(key, None)
            else:
                self._cache[namespace][key] = Item(
                    namespace=namespace,
                    key=key,
                    value=op.value,
                    created_at=current_time,
                    updated_at=current_time,
                )

                data = zlib.compress(
                    dill.dumps({"namespace": namespace, "key": key, "value": op.value})
                )

                _namespace = ":".join(namespace)
                async with self.async_session() as session:
                    async with session.begin():
                        item = self.cache_schema(
                            namespace=_namespace,
                            key=key,
                            value=data,
                            created_at=current_time,
                            updated_at=current_time,
                        )
                        await session.merge(item)

    def _prepare_ops(
        self, ops: Iterable[Op]
    ) -> Tuple[
        List[Result],
        Dict[Tuple[Tuple[str, ...], str], PutOp],
        Dict[int, Tuple[SearchOp, List[Tuple[Item, List[List[float]]]]]],
    ]:
        """复用原逻辑：拆分操作类型并初始化结果容器"""
        results: List[Result] = []
        put_ops: Dict[Tuple[Tuple[str, ...], str], PutOp] = {}
        search_ops: Dict[
            int, Tuple[SearchOp, List[Tuple[Item, List[List[float]]]]]
        ] = {}

        for i, op in enumerate(ops):
            if isinstance(op, GetOp):
                item = self._cache[op.namespace].get(op.key)
                results.append(item)
            elif isinstance(op, SearchOp):
                search_ops[i] = (op, self._filter_items(op))
                results.append(None)
            elif isinstance(op, ListNamespacesOp):
                results.append(self._handle_list_namespaces(op))
            elif isinstance(op, PutOp):
                put_ops[(op.namespace, op.key)] = op
                results.append(None)
            else:
                raise ValueError(f"Unknown operation type: {type(op)}")

        return results, put_ops, search_ops

    def _batch_search(self, ops, queryinmem_store, results) -> None:
        for i, (op, candidates) in ops.items():
            if not candidates:
                results[i] = []
                continue
            if op.query and queryinmem_store:
                query_embedding = queryinmem_store[op.query]
                flat_items, flat_vectors = [], []
                scoreless = []
                for item, vectors in candidates:
                    for vector in vectors:
                        flat_items.append(item)
                        flat_vectors.append(vector)
                    if not vectors:
                        scoreless.append(item)

                scores = _cosine_similarity(query_embedding, flat_vectors)
                sorted_results = sorted(
                    zip(scores, flat_items), key=lambda x: x[0], reverse=True
                )
                # max pooling
                seen: set[tuple[tuple[str, ...], str]] = set()
                kept: list[tuple[float | None, Item]] = []
                for score, item in sorted_results:
                    key = (item.namespace, item.key)
                    if key in seen:
                        continue
                    ix = len(seen)
                    seen.add(key)
                    if ix >= op.offset + op.limit:
                        break
                    if ix < op.offset:
                        continue

                    kept.append((score, item))
                if scoreless and len(kept) < op.limit:
                    # Corner case: if we request more items than what we have embedded,
                    # fill the rest with non-scored items
                    kept.extend(
                        (None, item) for item in scoreless[: op.limit - len(kept)]
                    )

                results[i] = [
                    SearchItem(
                        namespace=item.namespace,
                        key=item.key,
                        value=item.value,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                        score=float(score) if score is not None else None,
                    )
                    for score, item in kept
                ]
            else:
                results[i] = [
                    SearchItem(
                        namespace=item.namespace,
                        key=item.key,
                        value=item.value,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                    for (item, _) in candidates[op.offset : op.offset + op.limit]
                ]

    def _handle_list_namespaces(self, op: ListNamespacesOp) -> list[tuple[str, ...]]:
        all_namespaces = list(
            self._cache.keys()
        )  # Avoid collection size changing while iterating
        namespaces = all_namespaces
        if op.match_conditions:
            namespaces = [
                ns
                for ns in namespaces
                if all(_does_match(condition, ns) for condition in op.match_conditions)
            ]

        if op.max_depth is not None:
            namespaces = sorted({ns[: op.max_depth] for ns in namespaces})
        else:
            namespaces = sorted(namespaces)
        return namespaces[op.offset : op.offset + op.limit]

    async def _aclear(self, **kwargs: Any) -> None:
        # 确保初始化完成
        if self.is_async:
            await self._init_task
        """Clear cache."""
        stmt = select(self.cache_schema)
        async with self.async_session() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
            if rows:
                try:
                    for row in rows:
                        _, _, value, created_at, updated_at = row
                        value = dill.loads(zlib.decompress(value))
                        namespace = value.get("namespace")
                        key = value.get("key")
                        value = value.get("value")
                        if namespace and key and value:
                            if namespace not in self._cache:
                                self._cache[namespace] = {}
                            self._cache[namespace][key] = Item(
                                namespace=namespace,
                                key=key,
                                value=value,
                                created_at=created_at,
                                updated_at=updated_at,
                            )
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


@functools.lru_cache(maxsize=1)
def _check_numpy() -> bool:
    if bool(util.find_spec("numpy")):
        return True
    logger.warning(
        "NumPy not found in the current Python environment. "
        "The InMemoryStore will use a pure Python implementation for vector operations, "
        "which may significantly impact performance, especially for large datasets or frequent searches. "
        "For optimal speed and efficiency, consider installing NumPy: "
        "pip install numpy"
    )
    return False


def _cosine_similarity(X: list[float], Y: list[list[float]]) -> list[float]:
    """
    Compute cosine similarity between a vector X and a matrix Y.
    Lazy import numpy for efficiency.
    """
    if not Y:
        return []
    if _check_numpy():
        import numpy as np

        X_arr = np.array(X) if not isinstance(X, np.ndarray) else X
        Y_arr = np.array(Y) if not isinstance(Y, np.ndarray) else Y
        X_norm = np.linalg.norm(X_arr)
        Y_norm = np.linalg.norm(Y_arr, axis=1)

        # Avoid division by zero
        mask = Y_norm != 0
        similarities = np.zeros_like(Y_norm)
        similarities[mask] = np.dot(Y_arr[mask], X_arr) / (Y_norm[mask] * X_norm)
        return similarities.tolist()

    similarities = []
    for y in Y:
        dot_product = sum(a * b for a, b in zip(X, y))
        norm1 = sum(a * a for a in X) ** 0.5
        norm2 = sum(a * a for a in y) ** 0.5
        similarity = dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0
        similarities.append(similarity)

    return similarities


def _does_match(match_condition: MatchCondition, key: tuple[str, ...]) -> bool:
    """Whether a namespace key matches a match condition."""
    match_type = match_condition.match_type
    path = match_condition.path

    if len(key) < len(path):
        return False

    if match_type == "prefix":
        for k_elem, p_elem in zip(key, path):
            if p_elem == "*":
                continue  # Wildcard matches any element
            if k_elem != p_elem:
                return False
        return True
    elif match_type == "suffix":
        for k_elem, p_elem in zip(reversed(key), reversed(path)):
            if p_elem == "*":
                continue  # Wildcard matches any element
            if k_elem != p_elem:
                return False
        return True
    else:
        raise ValueError(f"Unsupported match type: {match_type}")


def _compare_values(item_value: Any, filter_value: Any) -> bool:
    """Compare values in a JSONB-like way, handling nested objects."""
    if isinstance(filter_value, dict):
        if any(k.startswith("$") for k in filter_value):
            return all(
                _apply_operator(item_value, op_key, op_value)
                for op_key, op_value in filter_value.items()
            )
        if not isinstance(item_value, dict):
            return False
        return all(
            _compare_values(item_value.get(k), v) for k, v in filter_value.items()
        )
    elif isinstance(filter_value, (list, tuple)):
        return (
            isinstance(item_value, (list, tuple))
            and len(item_value) == len(filter_value)
            and all(_compare_values(iv, fv) for iv, fv in zip(item_value, filter_value))
        )
    else:
        return item_value == filter_value


def _apply_operator(value: Any, operator: str, op_value: Any) -> bool:
    """Apply a comparison operator, matching PostgreSQL's JSONB behavior."""
    if operator == "$eq":
        return value == op_value
    elif operator == "$gt":
        return float(value) > float(op_value)
    elif operator == "$gte":
        return float(value) >= float(op_value)
    elif operator == "$lt":
        return float(value) < float(op_value)
    elif operator == "$lte":
        return float(value) <= float(op_value)
    elif operator == "$ne":
        return value != op_value
    else:
        raise ValueError(f"Unsupported operator: {operator}")
