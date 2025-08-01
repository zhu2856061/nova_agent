# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def handoff_to_planner():
    """Handoff to planner agent to do plan.协调者基于问题将任务交付给识别的意图对应团队"""
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to hand off to planner agent
    return
