# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import re
from typing import Annotated, Optional, Type

from langchain_core.tools import BaseTool, InjectedToolArg
from pydantic import BaseModel, Field

from .wechat_crawler import CrawlWechatTool
from .wechat_serper import SerpWechatTool

logger = logging.getLogger(__name__)


class SearchToolInput(BaseModel):
    """Input for the search tool."""

    query: str = Field(description="The query to search for")
    max_results: Annotated[int, InjectedToolArg] = Field(
        default=5, description="Maximum number of results to return"
    )


class WechatSearchTool(BaseTool):
    name: str = "wechat_search_tool"
    description: str = (
        "A search engine optimized for comprehensive, accurate, and trusted results. "
        "Useful for when you need to answer questions about current events."
    )
    args_schema: Type[BaseModel] = SearchToolInput

    def clean_markdown_links(self, text):
        # 移除各种类型的链接
        patterns = [
            # Markdown链接 [text](url)
            (r"\[([^\]]+)\]\([^)]+\)", r"\1"),
            # HTML链接
            (r'<a\s+[^>]*href="[^"]*"[^>]*>(.*?)</a>', r"\1"),
            # 纯URL链接
            (r"https?://\S+", ""),
            # 带括号的URL
            (r"\(https?://[^)]+\)", ""),
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)  # type: ignore

        return text.strip()  # type: ignore

    async def _arun(
        self,
        query: str,
        max_results: int = 5,
        summarize_model: Optional[str] = None,
    ):
        # 获取搜索结果
        serp_success = False
        serp_wechat_tool = SerpWechatTool()
        crawl_wechat_tool = CrawlWechatTool()

        all_results = []
        while not serp_success:
            search_result = await serp_wechat_tool.arun(
                {"query": query, "max_results": max_results}
            )
            serp_success = search_result.get("serp_success", False)
            results = search_result.get("results", [])
            if results:
                all_results.extend(results)

            if len(all_results) >= max_results:
                serp_success = True

        logger.info(f"Search results size: {len(all_results)}")

        # 获取网站内容
        crawl_tasks = []
        for result in all_results:
            crawl_tasks.append(crawl_wechat_tool.arun({"url": result["link"]}))

        crawl_results = await asyncio.gather(*crawl_tasks)

        final_results = []
        for i, response in enumerate(crawl_results):
            if isinstance(response, str):
                final_results.append(response)
            elif isinstance(response, dict):
                title = response.get("title")
                content = response.get("content")
                source = response.get("source")
                publish_time = response.get("publish_time")
                url = response.get("url")
                tmp = f"\n<title>\n{title}</title>\n\n<publish_time>\n{publish_time}</publish_time>\n\n<source>\n{source}</source>\n\n<url>\n{url}</url>\n\n<content>\n{content}</content>\n"

                final_results.append(tmp)

        if summarize_model is None:
            final_str = ""
            for line in final_results:
                final_str += f"<knowledge>\n{line}\n</knowledge>\n\n"

            return final_str

    def _run(self, query: str, max_results: int = 5):
        """Synchronous wrapper for the async crawl function."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return loop.create_task(self._arun(query, max_results))
            else:
                return loop.run_until_complete(self._arun(query, max_results))
        except RuntimeError:
            return asyncio.run(self._arun(query, max_results))
