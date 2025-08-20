# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
import re
from typing import Annotated, Dict, List, Optional, Type
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import (
    ContentTypeFilter,
    FilterChain,
    URLPatternFilter,
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, InjectedToolArg
from markdownify import markdownify as md
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

# from readabilipy import simple_json_from_html_string
from core.llms import get_llm_by_type
from core.prompts.deep_researcher import apply_system_prompt_template
from core.utils import get_today_str

logger = logging.getLogger(__name__)


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
        parts = re.split(image_pattern, self.to_markdown(self.html_content))

        for i, part in enumerate(parts):
            if i % 2 == 1:
                image_url = urljoin(self.url, part.strip())
                content.append({"type": "image_url", "image_url": {"url": image_url}})
            else:
                content.append({"type": "text", "text": part.strip()})

        return content


class Summary(BaseModel):
    summary: str = Field(description="The Summary of the content")
    key_excerpts: List = Field(description="The key excerpts of the content")


class CrawlToolInput(BaseModel):
    """Input schema for the CrawlTool."""

    url: str = Field(description="The URL to crawl")
    keywords: Optional[List] = Field(
        default=None, description="the keywords to look for in the content"
    )
    max_depth: Optional[int] = Field(
        default=1, ge=1, le=5, description="Maximum depth of pages to crawl"
    )
    max_pages: Optional[int] = Field(
        default=2, ge=1, le=20, description="Maximum num of pages to crawl"
    )

    # 验证URL格式
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if not parsed.scheme or parsed.scheme not in ["http", "https"]:
            raise ValueError("URL must start with http:// or https://")
        return v


class CrawlTool(BaseTool):
    name: str = "web_crawler"
    description: str = (
        "A tool that crawls websites and returns the content in markdown format"
    )
    args_schema: Type[BaseModel] = CrawlToolInput

    @staticmethod
    def remove_hyperlinks(html_content: str) -> str:
        """
        移除HTML内容中的超链接标签，只保留链接文本

        正则说明:
        - <a\\s+[^>]*?> : 匹配<a>标签的开始部分（包含所有属性）
        - (.*?) : 非贪婪匹配链接文本内容
        - </a> : 匹配</a>标签的结束部分
        - re.IGNORECASE : 忽略大小写
        - re.DOTALL : 让.匹配包括换行符在内的所有字符
        """
        if not html_content:
            return ""
        # 替换<a>标签为其内部文本
        cleaned_content = re.sub(
            r"<a\s+[^>]*?>(.*?)</a>",
            r"\1",  # 保留链接文本
            html_content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # 可选：进一步清理可能残留的空标签或多余空格
        cleaned_content = re.sub(r"<[^>]+>\s*<[^>]+>", " ", cleaned_content)
        cleaned_content = re.sub(r"\s+", " ", cleaned_content).strip()
        return cleaned_content

    async def _arun(
        self,
        url: str,
        keywords: list,
        max_depth: int = 1,
        max_pages: int = 2,
    ):
        # 验证输入参数
        try:
            url = CrawlToolInput.validate_url(url)
        except ValueError as e:
            logger.error(f"Invalid URL: {e}")
            return {"error": str(e), "url": url, "result": []}

        # 配置过滤器链 - 增强内容过滤
        filter_chain = FilterChain(
            [
                # Domain boundaries
                # URL patterns to include
                URLPatternFilter(patterns=["*guide*", "*tutorial*", "*blog*"]),
                # Content type filtering
                ContentTypeFilter(allowed_types=["text/html"]),
            ]
        )

        # 配置相关性评分器（处理keywords为None的情况）
        url_scorer = None
        if keywords and len(keywords) > 0:
            url_scorer = KeywordRelevanceScorer(keywords=keywords, weight=0.7)
            logger.info(f"Using keyword relevance scoring with: {keywords}")

        # # 配置爬虫运行参数
        run_conf = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                include_external=False,
                filter_chain=filter_chain,
                url_scorer=url_scorer,
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
            wait_for_images=True,
            scan_full_page=True,
            scroll_delay=0.5,
            cache_mode=CacheMode.BYPASS,
        )
        # 配置浏览器（优化渲染性能）
        browser_conf = BrowserConfig(
            browser_type="chromium",
            headless=True,
            extra_args=[  # 添加Chromium启动参数禁用图片
                "--blink-settings=imagesEnabled=false",
            ],
        )

        # Execute the crawl
        results = []
        crawled_urls: List[str] = []
        try:
            async with AsyncWebCrawler(config=browser_conf) as crawler:
                logger.info(
                    f"Starting crawl of {url} (max_depth: {max_depth}, max_pages: {max_pages})"
                )
                async for result in await crawler.arun(
                    url=url,
                    config=run_conf,
                    render=True,
                    render_timeout=60000,  # 渲染超时（毫秒）
                ):  # type: ignore
                    if not result.success:
                        logger.warning(f"Failed to crawl {result.url}: {result.error}")
                        continue
                    if result.url in crawled_urls:
                        logger.debug(f"Skipping duplicate URL: {result.url}")
                        continue
                    crawled_urls.append(result.url)

                    # 安全解析HTML内容
                    try:
                        # 替换可能有问题的simple_json_from_html_string，使用更健壮的处理
                        # 假设这里使用更可靠的解析方式
                        title = result.metadata.get("title", "No title")
                        # 或使用result.markdown如果生成了markdown
                        # 清理超链接（如果启用）
                        content = result.html

                        # if remove_links:
                        #     content = self.remove_hyperlinks(content)

                        content = Article(result.url, title, content).to_message()
                        results.append(
                            {
                                "url": result.url,
                                "title": title,
                                "content": content,
                                "metadata": {
                                    **result.metadata,
                                    "crawl_order": len(results) + 1,
                                    "is_success": result.success,
                                    "content_length": len(content) if content else 0,
                                },
                            }
                        )
                        logger.info(f"Successfully crawled {result.url})")

                    except Exception as e:
                        logger.error(
                            f"Error processing content from {result.url}: {str(e)}"
                        )
                        continue

            logger.info(f"Crawl completed. Total successful pages: {len(results)}")
            return {
                "url": url,
                "summary": f"Crawled {len(results)} out of {max_pages} requested pages",
                "result": results,
            }
        except Exception as e:
            logger.error(f"Critical error during crawling: {str(e)}", exc_info=True)
            return {"error": str(e), "url": url, "result": []}

    def _run(
        self,
        url: str,
        keywords: List,
        max_depth: int = 1,
        max_pages: int = 2,
    ):
        try:
            # 检查是否已有事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中运行（如FastAPI环境）
                return loop.run_until_complete(
                    self._arun(url, keywords, max_depth, max_pages)
                )
            else:
                # 没有事件循环时创建新的
                return asyncio.run(self._arun(url, keywords, max_depth, max_pages))
        except RuntimeError as e:
            logger.warning(f"Event loop issue: {e}. Falling back to basic async run.")
            return asyncio.run(self._arun(url, keywords, max_depth, max_pages))


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
                    await page.wait_for_selector(
                        ".result-op, .result.c-container", timeout=10_000
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
        return asyncio.run(self._arun(query, max_results))


class DeepResearcherToolInput(BaseModel):
    """Input for the search tool."""

    queries: List[str] = Field(description="The queries to search for")
    max_results: Annotated[int, InjectedToolArg] = Field(
        default=5, description="Maximum number of results to return"
    )
    runtime: Optional[Dict] = None


async def summarize_webpage(model: BaseChatModel, content: str):
    llm = model.with_structured_output(Summary)
    webpage_content = content

    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:
        try:
            result = await asyncio.wait_for(
                llm.ainvoke(
                    [
                        HumanMessage(
                            content=apply_system_prompt_template(
                                "summarize_webpage",
                                {
                                    "webpage_content": webpage_content,
                                    "date": get_today_str(),
                                },
                            )
                        )
                    ]
                ),
                timeout=200.0,
            )

            summary = result.summary  # type: ignore
            key_excerpts = "\n".join(result.key_excerpts)  # type: ignore

            return f"""<summary>\n{summary}\n</summary>\n\n<key_excerpts>\n{key_excerpts}\n</key_excerpts>"""  # type: ignore
        except Exception:
            token_limit = int(len(webpage_content) * 0.8)
            logger.warning(f"summarize reducing the chars to: {token_limit}")
            webpage_content = webpage_content[:token_limit]
            current_retry += 1

    return content


class DeepResearcherTool(BaseTool):
    name: str = "search_tool"
    description: str = (
        "A search engine optimized for comprehensive, accurate, and trusted results. "
        "Useful for when you need to answer questions about current events."
    )
    args_schema: Type[BaseModel] = DeepResearcherToolInput

    async def _arun(
        self,
        queries: List[str],
        max_results: Annotated[int, InjectedToolArg] = 5,
        runtime: Optional[RunnableConfig] = None,
    ):
        # 获取搜索结果
        search_tasks = []
        for query in queries:
            search_tasks.append(
                serp_tool.arun({"query": query, "max_results": max_results})
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
            keywords = result["query"].split()
            crawl_tasks.append(crawl_tool.arun({"url": url, "keywords": keywords}))

        crawl_results = await asyncio.gather(*crawl_tasks)

        for response in crawl_results:
            url = response["url"]
            result = response["result"]
            if url in unique_results:
                text = ""
                for tmp in result:
                    text += (
                        " ".join(
                            [
                                tx["text"]
                                for tx in tmp["content"]
                                if tx["type"] == "text"
                            ]
                        )
                        + "\n"
                    )

                unique_results[url]["raw_content"] = text

        if runtime is None:
            return unique_results

        # 基于LLM进行总结
        summarization_model = get_llm_by_type(runtime.get("summarize_model", "basic"))

        async def noop():
            return None

        summarization_tasks = [
            noop()
            if not result.get("raw_content")
            else summarize_webpage(
                summarization_model,
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
        runtime: Optional[RunnableConfig] = None,
    ):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(self._arun(queries, max_results, runtime))


# Create an instance
crawl_tool = CrawlTool()
serp_tool = SerpBaiduTool()
deep_researcher_tool = DeepResearcherTool()
