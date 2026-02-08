# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import re
from typing import Annotated, Dict, List, Optional, Type

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, InjectedToolArg
from pydantic import BaseModel, Field

from nova.llms import LLMS_Provider_Instance, Prompts_Provider_Instance
from nova.utils.common import get_today_str

from .baidu_serper import SerpBaiduTool
from .web_crawler import CrawlTool

logger = logging.getLogger(__name__)


class Summary(BaseModel):
    summary: str = Field(description="The Summary of the content")
    key_excerpts: List = Field(description="The key excerpts of the content")


class SearchToolInput(BaseModel):
    """Input for the search tool."""

    queries: List[str] = Field(description="The queries to search for")
    max_results: Annotated[int, InjectedToolArg] = Field(
        default=5, description="Maximum number of results to return"
    )
    runtime: Optional[Dict] = None


async def summarize_webpage(model: str, content: str):
    llm = LLMS_Provider_Instance.get_llm_by_type(model).with_structured_output(Summary)
    _webpage_content = content

    def _assemble_prompt(webpage_content):
        tmp = {
            "webpage_content": webpage_content,
            "date": get_today_str(),
        }
        _prompt_tamplate = Prompts_Provider_Instance.get_template(
            "researcher", "summarize_webpage"
        )
        return [
            HumanMessage(
                content=Prompts_Provider_Instance.prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ]

    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:
        try:
            result = await asyncio.wait_for(
                llm.ainvoke(_assemble_prompt(_webpage_content)),
                timeout=200.0,
            )

            summary = result.summary  # type: ignore
            key_excerpts = "\n".join(result.key_excerpts)  # type: ignore

            return f"""<summary>\n{summary}\n</summary>\n\n<key_excerpts>\n{key_excerpts}\n</key_excerpts>"""  # type: ignore
        except Exception:
            token_limit = int(len(_webpage_content) * 0.8)
            logger.warning(
                f"current_retry: {current_retry}, summarize reducing the chars to: {token_limit}"
            )
            _webpage_content = _webpage_content[:token_limit]
            current_retry += 1

    return content


class LLMSearchTool(BaseTool):
    name: str = "search_tool"
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
        queries: List[str],
        max_results: Annotated[int, InjectedToolArg] = 5,
        summarize_model: Optional[str] = None,
    ):
        serp_baidu_tool = SerpBaiduTool()
        web_crawler_tool = CrawlTool()
        # 获取搜索结果
        search_tasks = []
        for query in queries:
            search_tasks.append(
                serp_baidu_tool.arun({"query": query, "max_results": max_results})
            )
        search_results = await asyncio.gather(*search_tasks)

        # Format the search results and deduplicate results by URL
        unique_results = {}
        for response in search_results:
            for result in response["result"]:
                url = result["link"]
                if url not in unique_results:
                    unique_results[url] = {**result, "query": response["query"]}

        logger.info(f"Search results size: {len(unique_results)}")

        # 获取网站内容
        crawl_tasks = []
        for url, result in unique_results.items():
            crawl_tasks.append(web_crawler_tool.arun({"url": url}))

        crawl_results = await asyncio.gather(*crawl_tasks)

        for response in crawl_results:
            url = response["url"]
            result = response["result"]
            if url in unique_results:
                text = " ".join(
                    [
                        self.clean_markdown_links(tx["text"])
                        for tx in result["content"]
                        if tx["type"] == "text"
                    ]
                )

                unique_results[url]["raw_content"] = text

        if summarize_model is None:
            return unique_results

        async def noop():
            return None

        summarization_tasks = [
            noop()
            if not result.get("raw_content")
            else summarize_webpage(
                summarize_model,
                "**query**: "
                + result["query"]
                + "\n\n"
                + "**title**: "
                + result["title"]
                + "\n\n"
                + "**abstract**: "
                + result["abstract"]
                + "\n\n"
                + "**content**: "
                + result["raw_content"],
            )
            for result in unique_results.values()
        ]

        summaries = await asyncio.gather(*summarization_tasks)
        summarized_results = {
            url: {
                "title": result["title"],
                "content": result["raw_content"] if summary is None else summary,
            }
            for url, result, summary in zip(
                unique_results.keys(), unique_results.values(), summaries
            )
        }

        formatted_output = "Search results: \n\n"
        for i, (url, result) in enumerate(summarized_results.items()):
            formatted_output += f"\n\n--- SOURCE {i + 1}: {result['title']} ---\n"
            formatted_output += f"URL: {url}\n\n"
            formatted_output += f"SUMMARY:\n{result['content']}\n\n"
            formatted_output += "\n\n" + "-" * 80 + "\n"

        if summarized_results:
            return formatted_output
        else:
            return "No valid search results found. Please try different search queries or use a different search API."

    def _run(
        self,
        queries: List[str],
        max_results: int = 5,
        summarize_model: Optional[str] = None,
    ):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(self._arun(queries, max_results, summarize_model))
