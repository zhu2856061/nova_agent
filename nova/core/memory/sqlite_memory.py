# -*- coding: utf-8 -*-
# @Time   : 2025/09/04 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import datetime
import functools
import logging
import sqlite3
import zlib
from importlib import util
from pathlib import Path, PosixPath
from threading import Lock
from typing import Any, Dict, Iterable, List, Tuple, Union

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

logger = logging.getLogger(__name__)


class SQLiteStore(BaseStore):
    """
    SQLite-backed store with persistent key-value storage and optional vector search.

    核心：
    1. 使用SQLite数据库实现数据持久化
    2. 设计数据表存储键值数据
    3. 保持与InMemoryStore完全兼容的API接口
    """

    def __init__(
        self, database_path: Union[str, PosixPath], *, index: IndexConfig | None = None
    ) -> None:
        """
        初始化SQLiteStore

        Args:
            db_path: SQLite数据库文件路径（默认：langchain_store.db）
            index: 向量索引配置（同InMemoryStore）
        """
        # 初始化数据库连接
        self._cache = {}
        self.lock = Lock()
        self.database_path = Path(database_path)
        if self.database_path.exists():
            self._clear()
        else:
            conn = sqlite3.connect(
                self.database_path,
                check_same_thread=False,  # 允许跨线程访问（需注意线程安全）
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )

            cursor = conn.cursor()
            with self.lock:
                # 1. 键值数据表：存储命名空间、键、值及时间戳
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS key_value_store (
                    namespace TEXT NOT NULL,  -- 命名空间（tuple转字符串存储，如"users:123"）
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,  -- zlib.compress 序列化（需在put/get时序列化/反序列化）
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (namespace, key)
                )""")

                conn.commit()
                conn.close()

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        """批量处理操作（同步版）：同InMemoryStore接口"""
        results, put_ops, search_ops = self._prepare_ops(ops)

        # 处理搜索操作
        if search_ops:
            query_embeddings = None
            self._batch_search(search_ops, query_embeddings, results)

        self._apply_put_ops(put_ops)

        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """批量处理操作（异步版）：同InMemoryStore接口"""
        results, put_ops, search_ops = self._prepare_ops(ops)

        # 处理搜索操作（异步嵌入）
        if search_ops:
            query_embeddings = None
            self._batch_search(search_ops, query_embeddings, results)

        self._apply_put_ops(put_ops)

        return results

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
    def _apply_put_ops(self, put_ops: Dict[Tuple[Tuple[str, ...], str], PutOp]) -> None:
        """
        应用写入操作到SQLite（替代内存字典更新）
        支持新增/更新/删除（value为None时删除）
        """
        current_time = datetime.datetime.now(datetime.timezone.utc)
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

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
                with self.lock:
                    cursor.execute(
                        """
                    INSERT INTO key_value_store 
                    (namespace, key, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(namespace, key) DO UPDATE SET
                        value = ?,
                        updated_at = ?
                    """,
                        (
                            _namespace,
                            key,
                            data,
                            current_time,
                            current_time,
                            data,
                            current_time,  # 更新时的参数
                        ),
                    )
        conn.commit()
        conn.close()

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

    def _clear(self, **kwargs: Any) -> None:
        """Clear cache."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        with self.lock:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS key_value_store (
                    namespace TEXT NOT NULL,  -- 命名空间（tuple转字符串存储，如"users:123"）
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,  -- zlib.compress 序列化（需在put/get时序列化/反序列化）
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (namespace, key)
                )""")

            cursor.execute(
                "SELECT namespace, key, value, created_at, updated_at FROM key_value_store"
            )
            rows = cursor.fetchall()
            conn.commit()
            conn.close()

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
