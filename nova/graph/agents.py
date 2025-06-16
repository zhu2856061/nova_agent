# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

from langgraph.prebuilt import create_react_agent

from nova.llms import get_llm_by_type
from nova.tools import (
    bash_execute_tool,
    python_repl_tool,
    search_tool,
)

from .template import apply_system_prompt_template


# 🚀Create agents using configured LLM types
def create_agent(agent_type: str, tools: list, prompt_template: str):
    def _assemble_prompt(state):
        system_messages = apply_system_prompt_template(prompt_template, state)

        return system_messages + state["messages"]

    return create_react_agent(
        get_llm_by_type(agent_type),
        tools=tools,
        prompt=lambda _: _assemble_prompt(_),
        # debug=True,
    )


# 💡 research agent
research_agent = create_agent(
    agent_type="BASIC",
    tools=[search_tool],
    prompt_template="researcher",
)

# 💡 coder agent
coder_agent = create_agent(
    agent_type="BASIC",
    tools=[python_repl_tool, bash_execute_tool],
    prompt_template="coder",
)
