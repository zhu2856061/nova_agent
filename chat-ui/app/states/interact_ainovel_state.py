# -*- coding: utf-8 -*-
# @Time   : 2025/09/24 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
from dataclasses import dataclass
from typing import Any, Optional

import reflex as rx

from app.api.agent_api import (
    AGENT_AINOVEL_CHAPTER_BLUEPRINT_BACKEND_URL,
    AGENT_AINOVEL_CHARATER_DYNAMICS_BACKEND_URL,
    AGENT_AINOVEL_CORE_SEED_BACKEND_URL,
    AGENT_AINOVEL_EXTRACT_SETTING_BACKEND_URL,
    AGENT_AINOVEL_PLOT_ARCH_BACKEND_URL,
    AGENT_AINOVEL_SUMMARIZE_ACRHITECTURE_BACKEND_URL,
    AGENT_AINOVEL_WORLD_BUILDING_BACKEND_URL,
    get_agent_api,
)
from app.states.state import (
    _DEFAULT_NAME,
    _SELECTED_MODELS,
    _TASK_DIR,
    Parameters,
    State,
)

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class NovelStepMenu:
    value: str  # 标签唯一标识（用于切换）
    label: str  # 标签显示文本
    content: str  # 标签对应的内容组件（延迟渲染）
    disabled: bool = False  # 是否禁用标签
    icon: Optional[str] = None  # 标签图标（可选）
    component: Optional[rx.Component] = None


class InteractAiNovelState(State):
    unique_id = "Interact - AiNovel"
    _default_name = _DEFAULT_NAME

    novel_tabs: list[NovelStepMenu] = [
        NovelStepMenu(
            value="extract_setting",
            label="抽取设定",
            icon="brain",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
        NovelStepMenu(
            value="core_seed",
            label="核心种子",
            icon="gpu",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
        NovelStepMenu(
            value="character_dynamics",
            label="角色设定",
            icon="bike",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
        NovelStepMenu(
            value="world_building",
            label="世界观构建",
            icon="earth",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
        NovelStepMenu(
            value="plot_arch",
            label="情节架构",
            icon="layout-list",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
        NovelStepMenu(
            value="chapter_blueprint",
            label="章节目录",
            icon="list-tree",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
        NovelStepMenu(
            value="chapter_draft",
            label="章节内容",
            icon="clipboard-pen-line",  # 图标（Reflex内置图标名）
            content="editor",  # 聊天组件（需实现）
        ),
    ]

    params_fields: list[Parameters] = [
        Parameters(
            mkey="architecture_model",
            mtype="select",
            mvalue="basic_no_thinking",
            mvaluetype="str",
            mselected=_SELECTED_MODELS,
        ),
    ]

    # 状态变量
    current_chat = _default_name
    current_tab = "extract_setting"
    saving: bool = False

    _workspace = {current_chat: {}}  # 存储每个工作区的内容
    for item in novel_tabs:
        _workspace[current_chat][item.value] = {
            "input_content": "",
            "output_content": "",
            "final_content": "",
        }

    @rx.var
    def get_input_content(self) -> str:
        return self._workspace[self.current_chat][self.current_tab]["input_content"]

    @rx.var
    def get_output_content(self) -> str:
        return self._workspace[self.current_chat][self.current_tab]["output_content"]

    @rx.var
    def get_final_content(self) -> str:
        return self._workspace[self.current_chat][self.current_tab]["final_content"]

    @rx.event
    def change_tab_value(self, val):
        self.current_tab = val

    @rx.event
    def update_params_fields(self, form_data: dict[str, Any]):
        for k, v in form_data.items():
            for item in self.params_fields:
                if item.mkey == k:
                    if item.mvaluetype == "float":
                        item.mvalue = float(v)
                    elif item.mvaluetype == "int":
                        item.mvalue = int(v)
                    else:
                        item.mvalue = v
        logger.info(f"change settings, {self.params_fields}")

    @rx.event
    def create_chat(self, form_data: dict[str, Any]):
        """Create a new chat."""
        # Add the new chat to the list of chats.
        new_chat_name = form_data["new_chat_name"]
        self.current_chat = new_chat_name

        self._workspace[self.current_chat] = {}
        for item in self.novel_tabs:
            self._workspace[self.current_chat][item.value] = {
                "input_content": "",
                "output_content": "",
                "final_content": "",
            }

        self.is_new_chat_modal_open = False

    @rx.event
    def delete_chat(self, name: str):
        """Delete the current chat."""
        if name not in self._workspace:
            return
        del self._workspace[name]

        if len(self._workspace) == 0:
            self._workspace[self._default_name] = {}
            for item in self.novel_tabs:
                self._workspace[self._default_name][item.value] = {
                    "input_content": "",
                    "output_content": "",
                    "final_content": "",
                }

        if self.current_chat not in self._workspace:
            self.current_chat = list(self._workspace.keys())[0]

    @rx.event
    def set_chat_name(self, name: str):
        self.current_chat = name

    @rx.var
    def get_chat_names(self) -> list[str]:
        return list(self._workspace.keys())

    @rx.event
    def set_input_content(self, value: str):
        self._workspace[self.current_chat][self.current_tab]["input_content"] = value

    #
    @rx.event
    def set_final_content(self, value: str):
        self._workspace[self.current_chat][self.current_tab]["final_content"] = value

    # 保存输出内容
    @rx.event
    def save_final_content(self, form_data: dict[str, Any]):
        """保存输出内容的逻辑"""
        self.saving = True
        # 示例：保存到本地存储（或提交到后端）
        answer = form_data["answer"]
        if self.current_tab == "extract_setting":
            _event_name = "novel_extract_setting"
        elif self.current_tab == "core_seed":
            _event_name = "novel_core_seed"
        elif self.current_tab == "character_dynamics":
            _event_name = "novel_character_dynamics"
        elif self.current_tab == "world_building":
            _event_name = "novel_world_building"
        elif self.current_tab == "plot_arch":
            _event_name = "novel_plot_arch"
        elif self.current_tab == "chapter_blueprint":
            _event_name = "novel_chapter_blueprint"
        elif self.current_tab == "summarize_architecture":
            _event_name = "novel_summarize_architecture"

        if answer:
            # 这里可以替换为实际保存逻辑（如API调用、数据库存储等）
            #
            # 获取输出内容
            with open(f"{_TASK_DIR}/{self.current_chat}/{_event_name}.md", "w") as f:
                f.write(answer)
            yield rx.toast("内容已成功保存")
        else:
            yield rx.toast("没有可保存的内容", status="warning")
        self.saving = False

    @rx.event
    async def process_question(self, form_data: dict[str, Any]):
        try:
            question = form_data["question"]
            if not question:
                question = ""
            config = {}
            for item in self.params_fields:
                config[item.mkey] = item.mvalue

            self.processing = True

            # 初始化
            messages = {"role": "user", "content": question}

            _content_len = 0
            if self.current_tab == "extract_setting":
                _url = AGENT_AINOVEL_EXTRACT_SETTING_BACKEND_URL
                _event_name = "novel_extract_setting"
            elif self.current_tab == "core_seed":
                _url = AGENT_AINOVEL_CORE_SEED_BACKEND_URL
                _event_name = "novel_core_seed"
            elif self.current_tab == "character_dynamics":
                _url = AGENT_AINOVEL_CHARATER_DYNAMICS_BACKEND_URL
                _event_name = "novel_character_dynamics"
            elif self.current_tab == "world_building":
                _url = AGENT_AINOVEL_WORLD_BUILDING_BACKEND_URL
                _event_name = "novel_world_building"
            elif self.current_tab == "plot_arch":
                _url = AGENT_AINOVEL_PLOT_ARCH_BACKEND_URL
                _event_name = "novel_plot_arch"
            elif self.current_tab == "chapter_blueprint":
                _url = AGENT_AINOVEL_CHAPTER_BLUEPRINT_BACKEND_URL
                _event_name = "novel_chapter_blueprint"
            elif self.current_tab == "summarize_architecture":
                _url = AGENT_AINOVEL_SUMMARIZE_ACRHITECTURE_BACKEND_URL
                _event_name = "novel_summarize_architecture"

            async for item in get_agent_api(
                _url,
                self.current_chat,
                {"messages": messages, "user_guidance": question},
                config,
                {"task_name": "ai_novel", "result": question},
            ):  # type: ignore
                content = item["content"]

                # 🔹 处理 System 消息（如任务状态、工具调用）
                if item["type"] in ["system", "error"]:
                    if item["type"] == "error":
                        self._workspace[self.current_chat][self.current_tab][
                            "output_content"
                        ] += f"<span style='color:red'>{content}</span>"

                    else:
                        self._workspace[self.current_chat][self.current_tab][
                            "output_content"
                        ] += content

                elif item["type"] == "chat_start":
                    self._workspace[self.current_chat][self.current_tab][
                        "output_content"
                    ] += content

                elif item["type"] == "chat_end":
                    if isinstance(content, dict):
                        _reasoning_content = content["reasoning_content"]
                        _content = content["content"]
                        _tool_calls = content["tool_calls"]

                        if _content_len > 0:
                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] = self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ][:-_content_len]
                            _content_len = 0

                        if _reasoning_content:
                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += f"📝 思考过程\n\n{_reasoning_content}\n\n"

                        if _tool_calls:
                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += f"📝 工具入参\n\n{_tool_calls}\n\n"

                        if _content.strip():
                            self._workspace[self.current_chat][self.current_tab][
                                "output_content"
                            ] += f"📘 【Answer】\n\n{_content} \n\n"

                elif item["type"] == "answer":
                    self._workspace[self.current_chat][self.current_tab][
                        "output_content"
                    ] += content
                    _content_len += len(content)

                elif item["type"] == "thought":
                    self._workspace[self.current_chat][self.current_tab][
                        "output_content"
                    ] += content
                    _content_len += len(content)

                yield

            # 获取输出内容
            with open(f"{_TASK_DIR}/{self.current_chat}/{_event_name}.md", "r") as f:
                self._workspace[self.current_chat][self.current_tab][
                    "final_content"
                ] = f.read()

            # Toggle the processing flag.
            self.processing = False
        except Exception as e:
            logger.error(e)
            self.processing = False
            yield rx.toast("处理失败", status="error")

    @rx.event
    async def process_diagnose(self):
        pass

    @rx.event
    async def process_feedback(self):
        pass

    @rx.event
    async def process_one_click(self):
        pass
