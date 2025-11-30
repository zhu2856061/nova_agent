from langchain_core.prompts import PromptTemplate

from nova import CONF


def apply_prompt_template(template, state={}) -> str:
    _prompt = PromptTemplate.from_template(template=template).format(**state)
    return _prompt


def get_prompt(task, current_tab, dir=None):
    if not dir:
        _PROMPT_DIR = CONF["SYSTEM"]["prompt_template_dir"]
    else:
        _PROMPT_DIR = dir
    with open(f"{_PROMPT_DIR}/{task}/{current_tab}.md") as f:
        prompt_content = f.read()
    return prompt_content
