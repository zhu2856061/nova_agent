# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .llm import LLMSProvider
from .qwen3_embeddings import Qwen3EmbeddingsProvider
from .skill_hook import SkillsProvider
from .super_agent_hooks import SuperAgentHooks
from .template import PromptsProvider

_singleton_llms_instance: LLMSProvider | None = None
_singleton_template_instance: PromptsProvider | None = None

_singleton_super_agent_hooks_instance: SuperAgentHooks | None = None
_singleton_skill_provider_instance: SkillsProvider | None = None

_singleton_qwen3_embeddings_instance: Qwen3EmbeddingsProvider | None = None


def get_llms_provider() -> LLMSProvider:
    global _singleton_llms_instance
    if _singleton_llms_instance is None:
        _singleton_llms_instance = LLMSProvider(CONF.LLM)
    return _singleton_llms_instance


def get_prompts_provider() -> PromptsProvider:
    global _singleton_template_instance
    if _singleton_template_instance is None:
        _singleton_template_instance = PromptsProvider(CONF.SYSTEM.prompt_template_dir)
    return _singleton_template_instance


# 全局变量
def get_super_agent_hooks() -> SuperAgentHooks:
    global _singleton_super_agent_hooks_instance
    if _singleton_super_agent_hooks_instance is None:
        _singleton_super_agent_hooks_instance = SuperAgentHooks(
            CONF.HOOK.Agent_Node_Hooks
        )
    return _singleton_super_agent_hooks_instance


def get_skill_provider() -> SkillsProvider:
    global _singleton_skill_provider_instance
    if _singleton_skill_provider_instance is None:
        _singleton_skill_provider_instance = SkillsProvider(CONF.SYSTEM.skill_dir)
    return _singleton_skill_provider_instance


def get_qwen3_embeddings_provider() -> Qwen3EmbeddingsProvider:
    global _singleton_qwen3_embeddings_instance
    if _singleton_qwen3_embeddings_instance is None:
        _singleton_qwen3_embeddings_instance = Qwen3EmbeddingsProvider(
            configs=CONF.EMBEDDING.model_list,
            default_model_name=CONF.EMBEDDING.default_model_name,
        )
    return _singleton_qwen3_embeddings_instance
