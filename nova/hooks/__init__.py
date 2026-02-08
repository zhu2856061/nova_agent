# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .agent_hooks import AgentHooks

# 全局变量
Agent_Hooks_Instance = AgentHooks(CONF.HOOK.Agent_Node_Hooks)
