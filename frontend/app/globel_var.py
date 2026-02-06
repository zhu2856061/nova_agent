# # -*- coding: utf-8 -*-
# # @Time   : 2025/09/24 10:24
# # @Author : zip
# # @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import json
import os

from app.components.common.context_settings import Parameters
from app.components.common.sidebar_components import SideMenu
from app.components.common.tab_components import TabMenu

_SELECTED_MODELS = ["basic", "reasoning", "basic_no_thinking", "deepseek", "gemini"]
MENUS = [
    SideMenu(
        title="Chat",
        icon="message-circle-more",
        children=[
            SideMenu(
                title="llm",
                icon="message-circle-more",
                tobe="/agent/llm",
            ),
        ],
    ),
    SideMenu(
        title="Agent",
        icon="bot-message-square",
        children=[
            SideMenu(
                title="memorizer",
                icon="bot-message-square",
                tobe="/agent/memorizer",
            ),
            SideMenu(
                title="themeslicer",
                icon="bot-message-square",
                tobe="/agent/themeslicer",
            ),
            SideMenu(
                title="web_searcher",
                icon="bot-message-square",
                tobe="/agent/researcher",
            ),
            SideMenu(
                title="wechat_searcher",
                icon="bot-message-square",
                tobe="/agent/wechat_researcher",
            ),
            SideMenu(
                title="deepresearcher",
                icon="clipboard-list",
                tobe="/agent/deepresearcher",
            ),
            SideMenu(
                title="ainovel",
                icon="clipboard-list",
                tobe="/agent/ainovel",
            ),
            SideMenu(
                title="ainovel_architect",
                icon="bot-message-square",
                tobe="/agent/ainovel_architect",
            ),
            SideMenu(
                title="ainovel_chapter",
                icon="bot-message-square",
                tobe="/agent/ainovel_chapter",
            ),
        ],
    ),
    SideMenu(
        title="Interact",
        icon="layout-dashboard",
        children=[
            SideMenu(
                title="ainovel",
                icon="layout-dashboard",
                tobe="/interact/ainovel",
            ),
        ],
    ),
]

PARAMS_FIELDS = [
    Parameters(
        mkey="model",
        mtype="select",
        mvalue="basic",
        mvaluetype="str",
        mselected=_SELECTED_MODELS,
    ),
    Parameters(
        mkey="config",
        mtype="text_area",
        mvalue=json.dumps({"user_id": "merlin"}),
        mvaluetype="dict",
        mselected=None,
    ),
]

DEFAULT_CHAT = "Nova"
TASK_DIR = os.environ.get("TASK_DIR", "../merlin")
INSTERACT_TASK_DIR = os.path.join(TASK_DIR, "insteract")
PROMPT_DIR = os.environ.get("PROMPT_PATH", "../prompts")


AINOVEL_TABMENU = [
    TabMenu(
        value="extract_setting",
        label="抽取设定",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="core_seed",
        label="核心种子",
        icon="gpu",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="world_building",
        label="世界观构建",
        icon="earth",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="character_dynamics",
        label="角色设定",
        icon="bike",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="plot_arch",
        label="情节架构",
        icon="layout-list",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="chapter_blueprint",
        label="章节目录",
        icon="list-tree",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="build_architecture",
        label="汇总骨架",
        icon="calendar-plus",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="first_chapter",
        label="第一章节内容",
        icon="clipboard-pen-line",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="next_chapter",
        label="下一章节内容",
        icon="clipboard-pen-line",  # 图标（Reflex内置图标名）
        component="editor",
    ),
]


AINOVEL_PROMPT_TABMENU = [
    TabMenu(
        value="extract_setting",
        label="抽取设定",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="core_seed",
        label="种子设定",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="character_dynamics",
        label="角色设定",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="world_building",
        label="世界观构建",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="plot_arch",
        label="情节架构",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="chapter_blueprint",
        label="章节目录",
        icon="list-tree",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="first_chapter_draft",
        label="首章提示词",
        icon="brain",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="create_character_state",
        label="首章前创建角色状态",
        icon="bike",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="next_chapter_draft",
        label="下一章提示词",
        icon="gpu",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="global_summary",
        label="下一章前生成全局摘要",
        icon="earth",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="update_character_state",
        label="下一章前更新角色状态",
        icon="layout-list",  # 图标（Reflex内置图标名）
        component="editor",
    ),
    TabMenu(
        value="summarize_recent_chapters",
        label="下一章前生成近3章期概要",
        icon="list-tree",  # 图标（Reflex内置图标名）
        component="editor",
    ),
]
