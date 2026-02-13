# -*- coding: utf-8 -*-
# @Time   : 2025/08/12 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from nova.llms import LLMS_Provider_Instance

logger = logging.getLogger(__name__)
# ######################################################################################
# 配置


# ######################################################################################
# 全局变量


# ######################################################################################


def compile_deepagent_sample_agent():
    # chat graph
    model = LLMS_Provider_Instance.get_llm_by_type("basic")
    checkpointer = InMemorySaver()

    tmp = create_deep_agent(
        model=model,
        skills=["../skills/"],
        checkpointer=checkpointer,
    )
    png_bytes = tmp.get_graph(xray=True).draw_mermaid()
    logger.info(f"ainovel_architecture_agent: \n\n{png_bytes}")
    return tmp
