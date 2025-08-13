import asyncio
import re
from typing import List, Optional, Type
from urllib.parse import urljoin

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    URLPatternFilter,
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from langchain_core.tools import BaseTool
from markdownify import markdownify as md
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field
from readabilipy import simple_json_from_html_string


class Article:
    def __init__(self, url, title, html_content):
        self.url = url
        self.title = title
        self.html_content = html_content

    def to_markdown(self, including_title: bool = True) -> str:
        markdown = ""
        if including_title:
            markdown += f"# {self.title}\n\n"
        markdown += md(self.html_content)
        return markdown

    def to_message(self) -> list[str | dict]:
        image_pattern = r"!\[.*?\]\((.*?)\)"

        content = []
        parts = re.split(image_pattern, self.to_markdown())

        for i, part in enumerate(parts):
            if i % 2 == 1:
                image_url = urljoin(self.url, part.strip())
                content.append({"type": "image_url", "image_url": {"url": image_url}})
            else:
                content.append({"type": "text", "text": part.strip()})

        return content


class CrawlToolInput(BaseModel):
    """Input schema for the CrawlTool."""

    url: str = Field(description="The URL to crawl")
    keywords: Optional[List] = Field(
        default=None, description="the keywords to look for in the content"
    )
    max_depth: Optional[int] = Field(
        default=1, description="Maximum depth of pages to crawl"
    )
    max_pages: Optional[int] = Field(
        default=2, description="Maximum num of pages to crawl"
    )


class CrawlTool(BaseTool):
    name: str = "web_crawler"
    description: str = (
        "A tool that crawls websites and returns the content in markdown format"
    )
    args_schema: Type[BaseModel] = CrawlToolInput

    async def _arun(
        self,
        url: str,
        keywords: list,
        max_depth: int = 2,
        max_pages: int = 25,
    ):
        # Create a sophisticated filter chain
        filter_chain = FilterChain(
            [
                # Domain boundaries
                # URL patterns to include
                URLPatternFilter(patterns=["*guide*", "*tutorial*", "*blog*"]),
                # Content type filtering
                # ContentTypeFilter(allowed_types=["text/html"]),
            ]
        )

        # Create a relevance scorer
        keyword_scorer = KeywordRelevanceScorer(keywords=keywords, weight=0.7)

        # Set up the configuration
        run_conf = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                include_external=False,
                filter_chain=filter_chain,
                url_scorer=keyword_scorer,
                max_pages=max_pages,
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=True,
            verbose=True,
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(
                    threshold=0.4, threshold_type="fixed"
                )
            ),
        )
        """Asynchronously crawl a website and return the content."""
        browser_conf = BrowserConfig(browser_type="chromium", headless=True)

        # Execute the crawl
        results = []
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            async for result in await crawler.arun(url=url, config=run_conf):  # type: ignore
                if result.success:
                    article = simple_json_from_html_string(result.html)
                    print("===>", article.get("content"))
                    article = Article(
                        url=url,
                        title=article.get("title"),
                        html_content=article.get("content"),
                    )
                    content = article.to_message()
                    results.append(content)
        return results

    def _run(
        self,
        url: str,
        keywords: List,
        max_depth: int = 2,
        max_pages: int = 25,
    ):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(self._arun(url, keywords, max_depth, max_pages))


class SerpToolInput(BaseModel):
    """Input schema for the SerpTool."""

    query: str = Field(description="The query to search for")
    max_results: Optional[int] = Field(
        default=5, description="Maximum number of results to return"
    )


class SerpBaiduTool(BaseTool):
    name: str = "serp_tool"
    description: str = "A tool that searches the web and returns the top results"
    args_schema: Type[BaseModel] = SerpToolInput

    async def _arun(self, query: str, max_results: int):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # 调试时可设为 False
            page = await browser.new_page()
            await page.goto(f"https://www.baidu.com/s?wd={query}")

            results = []
            attempts = 0  # 防止无限滚动
            max_attempts = 10  # 最多尝试滚动加载的次数
            while len(results) < max_results and attempts < max_attempts:
                # 等待新加载的结果
                await page.wait_for_selector(
                    ".result-op, .result.c-container", timeout=5000
                )

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

            await browser.close()
            return results[:max_results]  # 返回指定数量的结果

    def _run(self, query: str, max_results: int):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(self._arun(query, max_results))


# Create an instance
crawl_tool = CrawlTool()
serp_tool = SerpBaiduTool()
