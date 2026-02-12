# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import os
import sys

sys.path.append("..")
os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.embeddings import Embeddings_Instances

embeddings = Embeddings_Instances.embed_query("质检效果")


# from langchain_openai import OpenAIEmbeddings

# # 初始化 Embedding 模型
# embeddings = OpenAIEmbeddings(
#     model="Qwen3-Embedding-8B-agent",  # 这里必须与 vLLM 启动时的 model 参数一致
#     base_url="http://10.25.71.72:15001/v1",  # 你的 vLLM 地址
#     api_key="",
#     check_embedding_ctx_length=False,  # Qwen 长度较长，建议关闭检查或手动设置
# )

# # 测试生成向量
# text = "你好，请将这段话转化为向量。"
# vector = embeddings.embed_query(text)
# print(f"向量维度: {len(vector)}")

"""
通用嵌入服务实现
支持通过API调用部署在各种平台上的嵌入模型
"""
