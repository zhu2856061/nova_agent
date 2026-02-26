# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .skill_hook import SkillsProvider

# 全局变量
Skill_Hooks_Instance = SkillsProvider(CONF.SYSTEM.skill_dir)
