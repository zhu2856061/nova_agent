import asyncio
import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"
from nova.core.llms import get_llm_by_type

print("\n===\n")
#


llm_instance = get_llm_by_type("basic")


chunks = []


async def async_generate_response():
    async for chunk in llm_instance.astream("what color is the sky?"):
        chunks.append(chunk)
        # print(chunk.response_metadata)
        print(chunk.content, end="|", flush=True)


asyncio.run(async_generate_response())
