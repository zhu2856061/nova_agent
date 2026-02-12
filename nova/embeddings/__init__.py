# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .qwen3_embeddings import Qwen3Embeddings

# 全局变量
Embeddings_Instances = Qwen3Embeddings(
    configs=CONF.EMBEDDING.model_list,
    default_model_name=CONF.EMBEDDING.default_model_name,
)
