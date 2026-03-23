# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.types import CrawlResult  # 关键：导入单结果类型
from langchain.tools import tool
from markdownify import markdownify as md
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


def clean_markdown_links(text):
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


WEB_CRAWL_TOOL_DESCRIPTION = """
A tool that crawls websites and returns the content in markdown format
Usage:
- The url parameter is the str

Examples:
- Search for "Python" on the web: `web_crawl(url="Python")`
"""


@tool("web_crawl", description=WEB_CRAWL_TOOL_DESCRIPTION)
async def web_crawl(url: str) -> str:
    def validate_url(v: str) -> str:
        parsed = urlparse(v)
        if not parsed.scheme or parsed.scheme not in ["http", "https"]:
            raise ValueError("URL must start with http:// or https://")
        return v

    try:
        url = validate_url(url)
        # 配置爬虫运行参数
        run_conf = CrawlerRunConfig(
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=True,
            verbose=True,
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(
                    threshold=0.4, threshold_type="fixed"
                )
            ),
            wait_for_images=False,
            scan_full_page=True,
            scroll_delay=0.5,
            cache_mode=CacheMode.BYPASS,
        )
        # 配置浏览器（优化渲染性能）
        browser_conf = BrowserConfig(
            browser_type="chromium",
            headless=True,  # 无头模式（生产环境推荐）
            extra_args=[
                "--blink-settings=imagesEnabled=false",  # 禁用图片加载（提速）
                "--disable-blink-features=AutomationControlled",  # 隐藏自动化标记
                "--no-sandbox",  # 容器环境必备（避免权限问题）
                "--disable-gpu",  # 禁用GPU加速（减少资源占用）
            ],
        )

        # Execute the crawl
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            logger.info(f"Starting crawl of {url}")

            # 关键修复：arun()返回CrawlResultContainer，无需async for
            crawl_result: CrawlResult = await crawler.arun(
                url=url,
                config=run_conf,
                render=True,  # 启用JS渲染（处理动态页面）
                render_timeout=20_000,  # 页面渲染超时
            )  # type: ignore

            # 4. 处理单条爬取结果
            if not crawl_result.success:
                error_msg = crawl_result.error_message or "Unknown error during crawl"
                logger.warning(f"Failed to crawl {url}: {error_msg}")
                return f"Failed to crawl {url}: {error_msg}"

            # 安全解析HTML内容
            try:
                # 替换可能有问题的simple_json_from_html_string，使用更健壮的处理
                # 假设这里使用更可靠的解析方式
                title = crawl_result.metadata.get("title") or "No Title"  # type: ignore
                # 或使用result.markdown如果生成了markdown
                # 清理超链接（如果启用）
                content = crawl_result.html or crawl_result.markdown or ""

                content = Article(crawl_result.url, title, content).to_markdown()

                # result = {
                #     "url": crawl_result.url,
                #     "title": title,
                #     "content": content,
                #     "metadata": {
                #         "publish_time": crawl_result.metadata.get(  # type: ignore
                #             "publish_time", "Unknown"
                #         ),
                #         "author": crawl_result.metadata.get("author", "Unknown"),  # type: ignore
                #         "is_success": crawl_result.success,
                #     },
                # }

                logger.info(
                    f"Crawl completed. Total successful pages: {crawl_result.url}"
                )
                return content

            except Exception as e:
                logger.error(
                    f"Content processing failed for {url}: {str(e)}",
                    exc_info=True,  # 打印完整堆栈，便于调试
                )
                return f"Content processing failed for {url}: {str(e)}"

    except ValueError as e:
        logger.error(f"Invalid URL: {e}")
        return f"error: {e}"


WEB_SERP_TOOL_DESCRIPTION = """
A tool that searches the web and returns the top results.
Usage:
- The query parameter is the search query

Examples:
- Search for "Python" on the web: `web_serp(query="Python")`
"""


@tool("web_serp", description=WEB_SERP_TOOL_DESCRIPTION)
async def web_serp(query: str) -> str:
    max_results = 3
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
        return "##".join(results[:max_results])


WEB_SEARCH_TOOL_DESCRIPTION = """
A search engine optimized for comprehensive, accurate, and trusted results.
Usage:
- The queries parameter is the list of search query

Examples:
- Search for "Python" on the web: `web_search(queries=["Python"])`
"""


@tool("web_search", description=WEB_SEARCH_TOOL_DESCRIPTION)
async def web_search(queries: list[str]) -> str:
    try:
        logger.info(f"开始网络检索：检索词: {queries}")

        # 获取搜索结果
        search_tasks = []
        for query in queries:
            search_tasks.append(web_serp.arun({"query": query, "max_results": 3}))
        search_results = await asyncio.gather(*search_tasks)

        unique_results = {}
        for response in search_results:
            for result in response["result"]:
                url = result["link"]
                if url not in unique_results:
                    unique_results[url] = {**result, "query": response["query"]}

        logger.info(f"Search results size: {len(unique_results)}")

        # 获取网站内容
        crawl_tasks = [
            web_crawl.arun({"url": url}) for url, result in unique_results.items()
        ]
        crawl_results = await asyncio.gather(*crawl_tasks)

        for response in crawl_results:
            url = response["url"]
            result = response["result"]
            if url in unique_results:
                text = " ".join(
                    [
                        clean_markdown_links(tx["text"])
                        for tx in result["content"]
                        if tx["type"] == "text"
                    ]
                )

                unique_results[url]["raw_content"] = text

        logger.info(f"网络检索完成，检索结果数量: {len(unique_results)}")
        return json.dumps(unique_results)

    except Exception as e:
        return f"Error: Unexpected error listing directory: {type(e).__name__}: {e}"


# @tool(description=WEB_SEARCH_TOOL_DESCRIPTION)
# async def web_search(
#     queries: list[str],
#     runtime: ToolRuntime[SuperContext, SuperState],
#     tool_call_id: Annotated[str, InjectedToolCallId],
# ) -> str:
#     try:
#         models = runtime.context.get("models")
#         summarize_model = None
#         if models and models.get("summarize"):
#             summarize_model = models.get("summarize")

#         logger.info(f"开始网络检索：检索词: {queries}")

#         serp_tool = SerpBaiduTool()
#         crawl_tool = CrawlTool()
#         # 获取搜索结果
#         search_tasks = []
#         for query in queries:
#             search_tasks.append(serp_tool.arun({"query": query, "max_results": 3}))
#         search_results = await asyncio.gather(*search_tasks)

#         unique_results = {}
#         for response in search_results:
#             for result in response["result"]:
#                 url = result["link"]
#                 if url not in unique_results:
#                     unique_results[url] = {**result, "query": response["query"]}

#         logger.info(f"Search results size: {len(unique_results)}")

#         # 获取网站内容
#         crawl_tasks = [
#             crawl_tool.arun({"url": url}) for url, result in unique_results.items()
#         ]
#         crawl_results = await asyncio.gather(*crawl_tasks)

#         for response in crawl_results:
#             url = response["url"]
#             result = response["result"]
#             if url in unique_results:
#                 text = " ".join(
#                     [
#                         clean_markdown_links(tx["text"])
#                         for tx in result["content"]
#                         if tx["type"] == "text"
#                     ]
#                 )

#                 unique_results[url]["raw_content"] = text
#         if summarize_model is None:
#             # 汇总信息
#             all_info = []
#             for result in unique_results.values():
#                 all_info.append(
#                     f"**query**: {result['query']}\n\n**title**: {result['title']}\n\n**abstract**: {result['abstract']}\n\n**content**: {result['raw_content']}\n"
#                 )

#             logger.info(f"网络检索完成，检索结果数量: {len(all_info)}")
#             return "\n\n---\n\n".join(all_info)

#         else:
#             all_info = []

#             async def noop():
#                 return None

#             thread_id = runtime.context.get("thread_id", "default")
#             summarization_tasks = [
#                 noop()
#                 if not result.get("raw_content")
#                 else context_summarize_agent.ainvoke(
#                     {"messages": [{"type": "human", "content": result["raw_content"]}]},  # type: ignore
#                     {"thread_id": thread_id, "model": summarize_model},  # type: ignore
#                 )
#                 for result in unique_results.values()
#             ]
#             summaries = await asyncio.gather(*summarization_tasks)

#             for result, summary in zip(unique_results.values(), summaries):
#                 all_info.append(
#                     f"**query**: {result['query']}\n\n**title**: {result['title']}\n\n**abstract**: {result['abstract']}\n\n**content**: {summary}\n"
#                 )

#             logger.info(f"网络检索完成，检索结果数量: {len(all_info)}")
#             return "\n\n---\n\n".join(all_info)

#     except Exception as e:
#         return f"Error: Unexpected error listing directory: {type(e).__name__}: {e}"
