# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
from typing import Optional, Type

from langchain_core.tools import BaseTool
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SerpBaiduToolInput(BaseModel):
    """Input schema for the SerpTool."""

    query: str = Field(description="The query to search for")
    max_results: Optional[int] = Field(
        default=5, description="Maximum number of results to return"
    )


class SerpBaiduTool(BaseTool):
    name: str = "serp_tool"
    description: str = "A tool that searches the web and returns the top results"
    args_schema: Type[BaseModel] = SerpBaiduToolInput

    async def _arun(self, query: str, max_results: int):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # 调试时可设为 False
            page = await browser.new_page()
            await page.goto(f"https://www.baidu.com/s?wd={query}")

            results = []
            attempts = 0  # 防止无限滚动
            max_attempts = 10  # 最多尝试滚动加载的次数
            while len(results) < max_results and attempts < max_attempts:
                try:
                    # 等待新加载的结果
                    await page.wait_for_selector(".result.c-container", timeout=20_000)

                    # 提取数据
                    current_results = await page.evaluate("""() => {
                        const items = Array.from(document.querySelectorAll(".result.c-container"));
                        return items.map(item => {
                            const titleElement = item.querySelector("h3 a"); // 标题
                            const abstractElement = item.querySelector(".summary-text_560AW, .c-span-last, .c-gap-top-small"); // 简介
                            const timeElement = item.querySelector(".cos-space-mr-3xs, .cos-color-text-minor"); // 时间
                            const sourceElement = item.querySelector(".cosc-source-text, .cos-line-clamp-1, .c-showurl-new"); // 来源

                            return {
                                title: titleElement?.innerText.trim() || "",
                                link: titleElement?.href || "",
                                abstract: abstractElement?.innerText.trim() || "",
                                time: timeElement?.innerText.trim() || "",
                                source: sourceElement?.innerText.trim() || ""
                            };
                        });
                    }""")
                    # 合并结果
                    results.extend(current_results)
                    # 如果结果还不够，尝试滚动加载更多
                    if len(results) < max_results:
                        await page.evaluate(
                            "window.scrollTo(0, document.body.scrollHeight)"
                        )
                        await page.wait_for_timeout(2000)  # 等待加载
                        attempts += 1
                    else:
                        break
                except Exception as e:
                    logger.error(f"async_playwright, Error occurred: {e}")
                    attempts += 1

            await browser.close()
            return {
                "query": query,
                "result": results[:max_results],  # 返回指定数量的结果
            }

    def _run(self, query: str, max_results: int):
        """Synchronous wrapper for the async crawl function."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return loop.create_task(self._arun(query, max_results))
            else:
                return loop.run_until_complete(self._arun(query, max_results))
        except Exception:
            return asyncio.run(self._arun(query, max_results))


# Create an instance
serp_baidu_tool = SerpBaiduTool()
