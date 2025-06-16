from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
from langchain_core.messages import SystemMessage

from nova import CONF

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(CONF["PROMPT"]["DIR"]),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str) -> str:
    try:
        template = env.get_template(f"{prompt_name}.md")
        return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")


def apply_system_prompt_template(prompt_name, state) -> list:
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }
    try:
        template = env.get_template(f"{prompt_name}.md")
        system_prompt = template.render(**state_vars)

        return [SystemMessage(system_prompt)]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
