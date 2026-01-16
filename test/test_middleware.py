import sys

sys.path.append("..")
import asyncio
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from langchain.agents import create_agent
from langchain.agents.middleware.todo import TodoListMiddleware
from langchain_core.messages import HumanMessage

from nova.llms.llm import get_llm_by_type

llm = get_llm_by_type("basic")


agent = create_agent(llm, middleware=[TodoListMiddleware()])


async def run():
    result = await agent.ainvoke(
        {"messages": [HumanMessage("Help me refactor my codebase")]}
    )
    print(result)


# Agent now has access to write_todos tool and todo state tracking
asyncio.run(run())
