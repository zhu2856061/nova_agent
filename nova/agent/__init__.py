# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from .ainovel import compile_ainovel_graph
from .ainovel_architect import (
    compile_ainovel_architecture_agent,
    compile_build_architecture_agent,
    compile_chapter_blueprint_agent,
    compile_character_dynamics_agent,
    compile_core_seed_agent,
    compile_extract_setting_agent,
    compile_plot_arch_agent,
    compile_world_building_agent,
)
from .ainovel_chapter import (
    compile_ainovel_chapter_agent,
    compile_first_chapter_draft_agent,
    compile_next_chapter_draft_agent,
)
from .chat import compile_chat_agent
from .deepresearcher import compile_deepresearcher_agent
from .memorizer import compile_memorizer_agent
from .researcher import compile_researcher_agent, compile_wechat_researcher_agent
from .theme_slicer import compile_theme_slicer_agent

# ======================================================================================
# 小说大纲
ainovel_architecture_agent = compile_ainovel_architecture_agent()
# 小说结构
build_architecture_agent = compile_build_architecture_agent()
# 小说章节
chapter_blueprint_agent = compile_chapter_blueprint_agent()
# 小说角色
character_dynamics_agent = compile_character_dynamics_agent()
# 小说种子
core_seed_agent = compile_core_seed_agent()
# 小说设定
extract_setting_agent = compile_extract_setting_agent()
# 小说结构
plot_arch_agent = compile_plot_arch_agent()
# 小说世界观
world_building_agent = compile_world_building_agent()
# 小说第一章节 draft
first_chapter_draft_agent = compile_first_chapter_draft_agent()
# 小说下一章节 draft
next_chapter_draft_agent = compile_next_chapter_draft_agent()
# 小说章节
ainovel_chapter_agent = compile_ainovel_chapter_agent(
    first_chapter_draft_agent, next_chapter_draft_agent
)
# 全流程写小说
ainovel_agent = compile_ainovel_graph()
# ======================================================================================

# 闲聊
chat_agent = compile_chat_agent()


# 深度研究
deepresearcher_agent = compile_deepresearcher_agent()

# 记忆demo agent
memorizer_agent = compile_memorizer_agent()

# 基于网站研究
researcher_agent = compile_researcher_agent()

# 基于微信研究
wechat_researcher_agent = compile_wechat_researcher_agent()

# 主题挖掘
theme_slicer_agent = compile_theme_slicer_agent()
