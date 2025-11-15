from langchain_core.prompts import PromptTemplate


def apply_prompt_template(template, state) -> str:
    _prompt = PromptTemplate.from_template(template=template).format(**state)
    return _prompt
