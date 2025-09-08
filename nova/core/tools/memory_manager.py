# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import asyncio
import uuid
from typing import Annotated, Optional, Type

from langchain_core.tools import BaseTool, InjectedToolArg
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field


class UpsertMemoryToolInput(BaseModel):
    content: str = Field(
        description="""The main content of the memory. For example:
            "User expressed interest in learning about French."
            """,
    )
    context: str = Field(
        description="""Additional context for the memory. For example:
            "This was mentioned while discussing career options in Europe."
            """,
    )


class UpsertMemoryTool(BaseTool):
    args_schema: Type[BaseModel] = UpsertMemoryToolInput
    description: str = "A tool for upserting memory into the store."
    name: str = "upsert_memory"

    async def _arun(self, content, context, trace_id, memory_id, user_id, store):
        mem_id = memory_id or uuid.uuid4()

        await store.aput(
            ("memories", user_id),
            key=trace_id + "|" + str(mem_id),
            value={"content": content, "context": context},
        )
        print(f"Stored memory {mem_id}")
        return f"Stored memory {mem_id}"

    def _run(self, content, context, trace_id, memory_id, user_id, store):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(
            self._arun(content, context, trace_id, memory_id, user_id, store)
        )


upsert_memory_tool = UpsertMemoryTool()


async def upsert_memory(
    content: str,
    context: str,
    *,
    memory_id: Optional[str] = None,
    # Hide these arguments from the model.
    user_id: Annotated[str, InjectedToolArg],
    store: Annotated[BaseStore, InjectedToolArg],
):
    """Upsert a memory in the database.

    If a memory conflicts with an existing one, then just UPDATE the
    existing one by passing in memory_id - don't create two memories
    that are the same. If the user corrects a memory, UPDATE it.

    Args:
        content: The main content of the memory. For example:
            "User expressed interest in learning about French."
        context: Additional context for the memory. For example:
            "This was mentioned while discussing career options in Europe."
        memory_id: ONLY PROVIDE IF UPDATING AN EXISTING MEMORY.
        The memory to overwrite.
    """

    mem_id = memory_id or uuid.uuid4()
    await store.aput(
        ("memories", user_id),
        key=str(mem_id),
        value={"content": content, "context": context},
    )

    return f"Stored memory {mem_id}"
