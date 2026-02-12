# -*- coding: utf-8 -*-
# @Time   : 2026/02/06
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Dict, List, Optional

import openai
from langchain_core.embeddings import Embeddings
from langchain_core.runnables.config import run_in_executor

from nova.model.config import EmbeddingModelConfig

# 获取日志记录器
logger = logging.getLogger(__name__)

# ######################################################################################
# 配置线程池（用于批量嵌入的并发处理）
DEFAULT_THREAD_POOL = ThreadPoolExecutor(max_workers=8)


class Qwen3Embeddings(Embeddings):
    """基于API的嵌入模型实现"""

    # Pydantic字段：支持配置校验和序列化

    def __init__(
        self,
        configs: List[EmbeddingModelConfig],
        default_model_name: Optional[str] = None,
    ):
        """
        初始化API嵌入模型
        Args:
            api_url: 嵌入服务的API地址
            api_key: API密钥（如果需要）
            model_name: 模型名称
            timeout: 请求超时时间（秒）
        """
        self.instances: Dict = {}
        self.default_model_name = None

        logger.info("初始化Qwen3系列嵌入模型...")

        # 创建OpenAI客户端实例
        for cfg in configs:
            try:
                client = openai.OpenAI(
                    api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout
                )
                # 测试客户端连通性（可选）
                self._test_client_connectivity(cfg.model_name, client)
                self.instances[cfg.model_name] = client
                logger.info(f"成功初始化模型实例: {cfg.model_name}")
            except Exception as e:
                logger.error(
                    f"初始化模型实例 {cfg.model_name} 失败: {str(e)}", exc_info=True
                )
                raise RuntimeError(f"模型实例初始化失败: {cfg.model_name}") from e

        # 设置默认模型
        if default_model_name:
            if default_model_name not in self.instances:
                raise ValueError(f"默认模型 {default_model_name} 不在配置列表中")
            self.default_model_name = default_model_name
        elif self.instances:
            # 无默认值时取第一个配置的模型
            self.default_model_name = next(iter(self.instances.keys()))
            logger.info(
                f"未指定默认模型，自动使用第一个实例: {self.default_model_name}"
            )

        logger.info(f"Qwen3嵌入模型初始化完成，共加载 {len(self.instances)} 个实例")

    def _test_client_connectivity(self, model_name: str, client: openai.OpenAI) -> None:
        """测试客户端连通性（轻量校验）"""
        try:
            # 发送一个空文本的嵌入请求（部分服务可能不支持，可注释）
            client.embeddings.create(input="", model=model_name)
        except Exception as e:
            # 捕获非致命错误，仅日志提示
            logger.warning(
                f"模型 {model_name} 连通性测试失败（可能不影响使用）: {str(e)}"
            )

    def _get_embedding(
        self, model_name: Optional[str], text: str, prompt: Optional[str] = None
    ) -> List[float]:
        """
        核心方法：获取单个文本的嵌入向量（内部调用）

        Args:
            model_name: 模型名称（None时使用默认模型）
            text: 输入文本
            prompt: 前缀提示词（可选，拼接在文本前）

        Returns:
            嵌入向量列表
        """
        # 处理模型名称
        target_model = model_name or self.default_model_name
        if not target_model or target_model not in self.instances:
            raise ValueError(
                f"模型名称无效: {model_name}，可用模型列表: {list(self.instances.keys())}"
            )

        # 预处理文本
        processed_text = (prompt + text) if prompt else text.strip()
        if not processed_text:
            logger.warning("输入文本为空，返回零向量")
            return []  # 空文本返回零向量（或根据需求调整）

        logger.debug(f"获取嵌入向量: {processed_text[:50]}...")
        try:
            client = self.instances[target_model]
            response = client.embeddings.create(
                input=processed_text, model=target_model
            )
            return response.data[0].embedding
        except openai.APIError as e:
            logger.error(
                f"API调用失败（模型: {target_model}）: {str(e)}", exc_info=True
            )
            raise RuntimeError(f"嵌入API调用失败: {e.message}") from e
        except Exception as e:
            logger.error(
                f"获取嵌入向量失败（模型: {target_model}）: {str(e)}", exc_info=True
            )
            raise RuntimeError(f"获取嵌入向量失败: {str(e)}") from e

    def embed_documents(
        self,
        texts: List[str],
        model_name: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> List[List[float]]:
        """
        批量嵌入文档列表（优化并发处理，提升性能）

        Args:
            texts: 待嵌入的文本列表
            model_name: 模型名称（None时使用默认模型）
            prompt: 前缀提示词（可选）

        Returns:
            嵌入向量列表（与输入文本一一对应）
        """
        if not texts:
            logger.warning("嵌入文档列表为空，返回空列表")
            return []

        logger.info(f"开始嵌入文档列表，共 {len(texts)} 个文档")
        embeddings = []

        # 使用线程池并发处理批量嵌入（提升效率）
        embed_func = partial(self._get_embedding, model_name, prompt=prompt)
        with DEFAULT_THREAD_POOL as executor:
            futures = [executor.submit(embed_func, text) for text in texts]
            for idx, future in enumerate(futures):
                try:
                    embeddings.append(future.result())
                    logger.debug(f"成功嵌入第 {idx + 1} 个文档")
                except Exception as e:
                    logger.error(
                        f"嵌入第 {idx + 1} 个文档失败: {str(e)}", exc_info=True
                    )
                    raise e

        logger.info(f"文档列表嵌入完成，成功生成 {len(embeddings)} 个向量")
        return embeddings

    def embed_query(
        self, text: str, model_name: Optional[str] = None, prompt: Optional[str] = None
    ) -> List[float]:
        """
        嵌入查询文本（符合LangChain标准接口）

        Args:
            text: 查询文本
            model_name: 模型名称（None时使用默认模型）
            prompt: 前缀提示词（可选）

        Returns:
            嵌入向量
        """
        logger.info("开始嵌入查询文本")
        return self._get_embedding(model_name, text, prompt)

    async def aembed_documents(
        self,
        texts: List[str],
        model_name: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> List[List[float]]:
        """异步批量嵌入文档（适配LangChain异步接口）"""
        return await run_in_executor(
            None, self.embed_documents, texts, model_name, prompt
        )

    async def aembed_query(
        self, text: str, model_name: Optional[str] = None, prompt: Optional[str] = None
    ) -> List[float]:
        """异步嵌入查询文本（适配LangChain异步接口）"""
        return await run_in_executor(None, self.embed_query, text, model_name, prompt)

    def __del__(self):
        """析构函数：关闭线程池"""
        if hasattr(self, "DEFAULT_THREAD_POOL"):
            DEFAULT_THREAD_POOL.shutdown(wait=False)
        logger.info("Qwen3嵌入模型实例已销毁")
