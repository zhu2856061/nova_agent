# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated, Optional, Type, cast

from langchain_core.tools import BaseTool, InjectedToolArg
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from nova.memory import SQLITESTORE

logger = logging.getLogger(__name__)


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

    async def _arun(self, content, context, memory_id, user_id):
        mem_id = memory_id or uuid.uuid4()

        await cast(BaseStore, SQLITESTORE).aput(
            ("memories", user_id),
            key=str(mem_id),
            value={"content": content, "context": context},
        )
        logger.info(f"Stored memory {mem_id}")
        return f"Stored memory {mem_id}"

    def _run(self, content, context, trace_id, memory_id, user_id):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(self._arun(content, context, memory_id, user_id))


upsert_memory_tool = UpsertMemoryTool()
