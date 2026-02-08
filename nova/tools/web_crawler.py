# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional, Type
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.types import CrawlResult  # 关键：导入单结果类型
from langchain_core.tools import BaseTool
from markdownify import markdownify as md
from pydantic import BaseModel, Field

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


class CrawlToolInput(BaseModel):
    """Input schema for the CrawlTool."""

    url: str = Field(description="The URL to crawl")

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

    async def _arun(self, url: str):
        # 验证输入参数
        try:
            url = CrawlToolInput.validate_url(url)
        except ValueError as e:
            logger.error(f"Invalid URL: {e}")
            return {"error": str(e), "url": url, "result": []}

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
        crawler: Optional[AsyncWebCrawler] = None
        try:
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
                    error_msg = (
                        crawl_result.error_message or "Unknown error during crawl"
                    )
                    logger.warning(f"Failed to crawl {url}: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "url": url,
                        "result": [],
                    }

                # 安全解析HTML内容
                try:
                    # 替换可能有问题的simple_json_from_html_string，使用更健壮的处理
                    # 假设这里使用更可靠的解析方式
                    title = crawl_result.metadata.get("title") or "No Title"  # type: ignore
                    # 或使用result.markdown如果生成了markdown
                    # 清理超链接（如果启用）
                    content = crawl_result.html or crawl_result.markdown or ""

                    # if remove_links:
                    #     content = self.remove_hyperlinks(content)

                    content = Article(crawl_result.url, title, content).to_message()

                    result = {
                        "url": crawl_result.url,
                        "title": title,
                        "content": content,
                        "metadata": {
                            "publish_time": crawl_result.metadata.get(  # type: ignore
                                "publish_time", "Unknown"
                            ),
                            "author": crawl_result.metadata.get("author", "Unknown"),  # type: ignore
                            "is_success": crawl_result.success,
                        },
                    }

                    logger.info(
                        f"Crawl completed. Total successful pages: {crawl_result.url}"
                    )
                    return {"url": url, "result": result}

                except Exception as e:
                    logger.error(
                        f"Content processing failed for {url}: {str(e)}",
                        exc_info=True,  # 打印完整堆栈，便于调试
                    )
                    return {
                        "success": False,
                        "error": f"Content processing error: {str(e)}",
                        "url": url,
                        "result": {},
                    }

        except Exception as e:
            logger.error(f"Critical error during crawling: {str(e)}", exc_info=True)
            return {"error": str(e), "url": url, "result": {}}

    def _run(self, url: str):
        try:
            # 检查是否已有事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中运行（如FastAPI环境）
                return loop.create_task(self._arun(url))
            else:
                # 没有事件循环时创建新的
                return loop.run_until_complete(self._arun(url))
        except Exception as e:
            logger.warning(f"Event loop issue: {e}. Falling back to basic async run.")
            return asyncio.run(self._arun(url))
