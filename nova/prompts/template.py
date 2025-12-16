# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from langchain_core.prompts import PromptTemplate

from nova import CONF


def apply_prompt_template(template, state={}) -> str:
    _prompt = PromptTemplate.from_template(template=template).format(**state)
    return _prompt


def get_prompt(task, current_tab, dir=None):
    if not dir:
        _prompt_dir = CONF["SYSTEM"]["prompt_template_dir"]
        _prompt_dir = f"{_prompt_dir}/{task}"
    else:
        _prompt_dir = f"{dir}"
    with open(f"{_prompt_dir}/{current_tab}.md") as f:
        prompt_content = f.read()
    return prompt_content
