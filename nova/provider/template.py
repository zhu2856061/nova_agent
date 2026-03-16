# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from langchain_core.prompts import PromptTemplate


class PromptsProvider:
    """
    提示模板，提供两个方法，一个用于应用模板，一个用于获取文件内容

    1. prompt_apply_template(self, template, state={}) -> str: 应用模板

    2. get_template(self, child_dir, current_name, dir=None): 获取文件内容
    """

    def __init__(self, prompt_template_dir) -> None:
        self.prompt_template_dir = prompt_template_dir

    def prompt_apply_template(self, template, state={}) -> str:
        # 应用模板
        _prompt = PromptTemplate.from_template(template=template).format(**state)
        return _prompt

    def get_template(self, child_dir, current_name, dir=None) -> str:
        # 获取文本

        if not dir:
            _template_dir = f"{self.prompt_template_dir}/{child_dir}"
        else:
            _template_dir = f"{dir}/{child_dir}"

        with open(f"{_template_dir}/{current_name}.md") as f:
            _content = f.read()

        return _content
