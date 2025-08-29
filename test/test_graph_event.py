# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import sys
import uuid

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.core.agent.researcher import researcher_agent

inputs = {
    "researcher_messages": [
        {
            "role": "user",
            "content": "请查询网络上的信息，深圳的最近一周内的经济新闻",
        }
    ],
}
context = {
    "trace_id": 123,
    "researcher_model": "basic",
    "summarize_model": "basic",
    "compress_research_model": "basic",
    "max_react_tool_calls": 2,
}
workflow_id = str(uuid.uuid4())


async def async_generate_response():
    async for event in researcher_agent.astream_events(
        inputs, context=context, version="v2"
    ):
        # if event["event"] != "on_chat_model_stream":
        #     print("====>", event["event"])
        #     print("====>", event)

        kind = event.get("event")
        data = event.get("data")
        name = event.get("name")
        metadata = event.get("metadata")
        node = (
            ""
            if (metadata.get("checkpoint_ns") is None)
            else metadata.get("checkpoint_ns").split(":")[0]
        )
        langgraph_step = (
            ""
            if (metadata.get("langgraph_step") is None)
            else str(metadata["langgraph_step"])
        )
        run_id = "" if (event.get("run_id") is None) else str(event["run_id"])

        if kind == "on_chain_start":
            ydata = {
                "event": "start_of_agent",
                "data": {
                    "agent_name": name,
                    "agent_id": f"{workflow_id}_{name}_{langgraph_step}",
                },
            }
        elif kind == "on_chain_end":
            ydata = {
                "event": "end_of_agent",
                "data": {
                    "agent_name": name,
                    "agent_id": f"{workflow_id}_{name}_{langgraph_step}",
                },
            }
        elif kind == "on_chat_model_start":
            ydata = {
                "event": "start_of_llm",
                "data": {"agent_name": node},
            }

        elif kind == "on_chat_model_end":
            ydata = {
                "event": "end_of_llm",
                "data": {"agent_name": node},
            }
        elif kind == "on_chat_model_stream":
            content = data["chunk"].content
            if content is None or content == "":
                if not data["chunk"].additional_kwargs.get("reasoning_content"):
                    # Skip empty messages
                    continue
                ydata = {
                    "event": "message",
                    "data": {
                        "message_id": data["chunk"].id,
                        "delta": {
                            "reasoning_content": (
                                data["chunk"].additional_kwargs["reasoning_content"]
                            )
                        },
                    },
                }
            else:
                ydata = {
                    "event": "message",
                    "data": {
                        "message_id": data["chunk"].id,
                        "delta": {"content": content},
                    },
                }

        elif kind == "on_tool_start":
            ydata = {
                "event": "tool_call",
                "data": {
                    "tool_call_id": f"{workflow_id}_{node}_{name}_{run_id}",
                    "tool_name": name,
                    "tool_input": data.get("input"),
                },
            }

        elif kind == "on_tool_end":
            ydata = {
                "event": "tool_call_result",
                "data": {
                    "tool_call_id": f"{workflow_id}_{node}_{name}_{run_id}",
                    "tool_name": name,
                    "tool_result": data["output"].content if data.get("output") else "",
                },
            }
        else:
            continue

        yield ydata


asyncio.run(async_generate_response())
