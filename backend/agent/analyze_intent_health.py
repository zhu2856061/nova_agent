# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from sklearn.metrics.pairwise import cosine_similarity

from nova.agent.utils import node_with_hooks
from nova.embeddings.qwen3_embeddings import qwen3_embeddings_instances
from nova.model.agent import Context, State

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


# 函数
async def analyze_intent_health(state: State, runtime: Runtime[Context]):
    """
    检查意图健康，其中输入列必须为： 标准问，相似问

    """

    _NODE_NAME = "analyze_intent_health"

    # 变量
    _thread_id = runtime.context.thread_id
    _model_name = runtime.context.model
    _csv_path = state.data["csv_path"]

    #
    _df = pd.read_csv(_csv_path)
    _intent_map = defaultdict(list)

    for _, row in _df.iterrows():
        _intent_map[row["标准问"]].append(row["相似问"])

    _intent_names = list(_intent_map.keys())
    _intent_centroids = []  # 存储每个意图的中心向量
    _report = []

    logger.info(f"正在处理 {len(_intent_names)} 个意图...")

    # 2. 计算内聚度 (Intra-intent Cohesion)
    for intent in _intent_names:
        queries = _intent_map[intent]
        embeddings = qwen3_embeddings_instances.embed_documents(_model_name, queries)

        # 计算该意图的中心点（质心）
        centroid = np.mean(embeddings, axis=0)
        _intent_centroids.append(centroid)

        # 计算所有相似问到中心点的平均相似度
        cohesion = np.mean(cosine_similarity([centroid], embeddings))  # type: ignore

        _report.append(
            {
                "意图名称": intent,
                "相似问数量": len(queries),
                "内聚度得分": round(cohesion, 4),
            }
        )

    # 3. 计算耦合度 (Inter-intent Coupling / Conflict)
    # 计算意图中心点之间的两两相似度矩阵
    dist_matrix = cosine_similarity(_intent_centroids)

    conflicts = []
    for i in range(len(_intent_names)):
        for j in range(i + 1, len(_intent_names)):
            similarity = dist_matrix[i][j]
            if similarity > 0.85:  # 高风险阈值
                conflicts.append(
                    {
                        "意图A": _intent_names[i],
                        "意图B": _intent_names[j],
                        "语义相似度": round(similarity, 4),
                        "建议": "建议合并或重新定义边界",
                    }
                )

    # 4. 输出结果
    report_df = pd.DataFrame(_report)
    conflict_df = pd.DataFrame(conflicts).sort_values(by="语义相似度", ascending=False)

    logger.info("\n--- 意图内聚度扫描 (得分越低越乱) ---")
    logger.info(report_df.sort_values(by="内聚度得分").head(10))  # 打印最乱的10个

    logger.info("\n--- 高风险冲突对扫描 (相似度越高越危险) ---")
    logger.info(conflict_df.head(10))

    return Command(
        goto="__end__",
        update={
            "code": 0,
            "err_message": "ok",
            "data": {"report_df": report_df, "conflict_df": conflict_df},
        },
    )


def compile_agent():
    # chat graph
    _agent = StateGraph(State, context_schema=Context)
    _agent.add_node(
        "analyze_intent_health",
        node_with_hooks(analyze_intent_health, "analyze_intent_health"),
    )
    _agent.add_edge(START, "analyze_intent_health")

    checkpointer = InMemorySaver()
    return _agent.compile(checkpointer=checkpointer)


analyze_intent_health_agent = compile_agent()
