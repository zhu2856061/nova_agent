# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.types import CrawlResult  # 关键：导入单结果类型
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import HumanMessage
from markdownify import markdownify as md
from playwright.async_api import Browser, BrowserContext, async_playwright

from nova.model.super_agent import SuperContext, SuperState
from nova.node import webpage_summarize_agent
from nova.utils.common import (
    truncate_if_too_long,
)
from nova.utils.url_fetcher import SogouUrlFetcher

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


@tool("wechat_crawl", description=WEB_CRAWL_TOOL_DESCRIPTION)
async def wechat_crawl(url: str) -> str:
    # 随机用户代理池 - 增加多样性
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Edg/137.0.0.0",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.6723.71 Mobile Safari/537.36",
    ]

    # 上次请求时间，用于控制请求频率
    last_request_time = 0
    # 最小请求间隔（秒）
    MIN_REQUEST_INTERVAL = 8
    sougou_url_fetcher = SogouUrlFetcher()

    # 控制请求频率，避免过快请求
    sougou_url_fetcher.control_request_rate(last_request_time, MIN_REQUEST_INTERVAL)

    # 随机选择用户代理
    user_agent = random.choice(USER_AGENTS)
    url = sougou_url_fetcher.get_real_url(url)
    logger.info(f"请求链接: {url}")

    if not url:
        logger.warning(f"无法获取真实链接: {url}")
        return f"无法获取真实链接: {url}"

    async with async_playwright() as p:
        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        try:
            # 启动浏览器，增强隐藏自动化特征
            launch_args = [
                "--disable-blink-features=AutomationControlled",  # 核心：禁用AutomationControlled标识
                "--disable-webdriver-detect",  # 禁用webdriver检测
                "--disable-features=IsolateOrigins,site-per-process",  # 关闭站点隔离（减少指纹差异）
                "--start-maximized",
                f"--user-agent={user_agent}",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-notifications",
                "--remote-debugging-port=0",
                "--ignore-certificate-errors",  # 避免证书错误中断请求
                "--disable-sync",  # 禁用Chrome同步（减少新设备标识）
            ]

            # 启动浏览器
            browser = await p.chromium.launch(
                headless=True,
                args=launch_args,
                slow_mo=random.randint(50, 200),  # 随机操作延迟
                # channel="chrome",  # 使用系统安装的Chrome（而非Playwright自带的精简版）
            )

            # 3. 创建上下文：补充指纹相关配置
            context = await browser.new_context(
                viewport={
                    "width": random.choice(
                        [1366, 1440, 1920]
                    ),  # 只选常见屏幕分辨率（避免异常值）
                    "height": random.choice([768, 900, 1080]),
                },
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],
                color_scheme=random.choice(["light", "dark"]),
                device_scale_factor=random.choice([1.0, 1.25, 1.5]),  # 常见缩放比例
                accept_downloads=False,
            )
            # 4. 注入反指纹脚本：修改Canvas、WebGL、navigator等关键标识
            await sougou_url_fetcher.inject_stealth_scripts(context)

            # 模拟真实用户的本地存储和cookie
            await sougou_url_fetcher.setup_fake_storage(context)

            page = await context.new_page()

            # 先访问微信首页，建立正常访问流程
            # await self._pre_visit(page)

            # 导航到文章页面，使用随机等待策略
            logger.info(f"Navigating to article: {url}")
            await page.goto(url)

            # 随机等待页面加载，模拟用户等待
            await sougou_url_fetcher._random_delay(1000, 3000)

            # 模拟用户滚动页面
            await sougou_url_fetcher.simulate_scrolling(page)

            # 等待页面完全加载
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

            # 再次随机滚动
            await sougou_url_fetcher.simulate_scrolling(page)
            await sougou_url_fetcher._random_delay(1000, 2000)

            # 检查是否触发反爬
            if "wechat.sogou.com/antispider" in page.url or "verify" in page.url:
                logger.warning("⚠️ Anti-spider page detected when accessing article")
                return f"# 提取文章内容失败，进入验证码网页了\n\n原文链接: {url}"

            # 提取文章内容
            # title = await sougou_url_fetcher.extract_title(page)
            # metadata = await sougou_url_fetcher.extract_metadata(page)
            content_html = await sougou_url_fetcher.extract_content(page)
            content_md = md(content_html)
            content_md = sougou_url_fetcher.remove_svg_data(content_md + "\n")

            # 组合完整的Markdown内容
            # full_md = f"# {title}\n\n"
            # full_md += f"**来源**: {metadata.get('source', '未知')}\n"
            # full_md += f"**发布时间**: {metadata.get('publish_time', '未知')}\n"
            # full_md += f"**原文链接**: {url}\n\n"
            # full_md += "---\n\n"
            # full_md += content_md
            # full_md = {
            #     "title": title,
            #     "content": content_md,
            #     "url": url,
            #     "source": metadata.get("source", "未知"),
            #     "publish_time": metadata.get("publish_time", "未知"),
            # }

            # 更新最后请求时间
            last_request_time = time.time()
            return content_md

        except Exception as e:
            logger.error(f"Error extracting article content: {str(e)}", exc_info=True)
            return f"# 提取文章内容失败\n\n错误信息: {str(e)}\n\n原文链接: {url}"
        finally:
            if context:
                await context.close()
            if browser and browser.is_connected():
                await browser.close()


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
        return json.dumps(results[:max_results], ensure_ascii=False)


@tool("wechat_serp", description=WEB_SERP_TOOL_DESCRIPTION)
async def wechat_serp(query: str) -> str:
    # 1. 配置浏览器参数（增强反爬）
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    results = []  # 存储最终结果
    current_page = 1  # 当前页码
    max_pages = 10  # 最大翻页次数（防止无限循环）
    serp_success = False  # 爬取状态标记
    max_results = 3

    async with async_playwright() as p:
        try:
            # 启动浏览器（无头模式，生产环境可用）
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",  # 隐藏自动化标记
                    "--start-maximized",
                    f"--user-agent={user_agent}",
                    "--no-sandbox",  # 容器环境必备，避免权限问题
                    "--disable-gpu",  # 禁用GPU加速，减少资源占用
                ],
                slow_mo=100,  # 操作延迟100ms，模拟真实用户
            )

            # 创建上下文（模拟真实浏览器环境）
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],  # 授予地理位置权限（可选，增强真实性）
            )
            page = await context.new_page()

            # 2. 首次访问搜索页（避免直接拼接URL被反爬）
            await page.goto("https://weixin.sogou.com/")
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(1.5, 2.5))  # 随机延迟

            # 3. 模拟手动输入关键词（而非URL传参，降低反爬风险）
            search_box = page.locator("#query")
            await search_box.wait_for(state="visible", timeout=20000)
            # 逐字输入（核心反爬：模拟真实打字）
            for char in query:
                await search_box.type(char, delay=random.uniform(80, 150))
                await asyncio.sleep(random.uniform(0.05, 0.1))

            # 点击搜索按钮（而非直接访问URL）
            submit_btn = page.locator("input[value='搜文章']")
            await submit_btn.wait_for(state="visible", timeout=10000)
            # 检查按钮是否可用（不包含disabled属性）
            is_disabled = await submit_btn.get_attribute("disabled")
            if is_disabled is not None:
                # 按钮不可用，尝试刷新或等待
                logger.warning("Submit button is disabled, waiting...")
                await asyncio.sleep(2)
                # 再次检查
                is_disabled = await submit_btn.get_attribute("disabled")
                if is_disabled is not None:
                    raise Exception("Submit button remains disabled, cannot proceed")

            # 执行点击操作
            await submit_btn.hover()
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(1.2, 2.0))

            # 4. 分页爬取主逻辑（直到获取目标结果或达到最大页数）
            while len(results) < max_results and current_page <= max_pages:
                logger.info(
                    f"=== Crawling page {current_page}, current results: {len(results)}/{max_results} ==="
                )

                # 5. 验证码处理（关键：避免爬取中断）
                if "weixin.sogou.com/antispider" in page.url:
                    logger.warning(
                        "⚠️ Sogou verification code detected! Manual handling required."
                    )
                    # # 方案1：手动验证（适合调试，生产环境需替换为自动打码）
                    # print(
                    #     "Please complete the verification in the browser (headless=False to see it), then press Enter..."
                    # )
                    # input()  # 暂停等待手动验证
                    # await page.wait_for_load_state("networkidle", timeout=30000)
                    # await asyncio.sleep(2)
                    continue  # 验证后重新提取当前页结果

                # 6. 提取当前页结果（修复元素定位：原定位器可能失效）
                try:
                    # 等待结果列表加载（确保元素存在）
                    await page.wait_for_selector(
                        ".news-box .news-list li", timeout=20000
                    )

                    # 使用evaluate提取数据（避免Playwright定位器跨页失效）
                    current_page_results = await page.evaluate("""() => {
                        const items = Array.from(document.querySelectorAll(".news-box .news-list li"));
                        return items.map(item => {
                            // 修复定位器：搜狗微信搜索的标准结构
                            const titleEl = item.querySelector(".txt-box h3 a");
                            const abstractEl = item.querySelector(".txt-box p.txt-info");
                            const sourceEl = item.querySelector(".s-p .all-time-y2");  // 来源（公众号名称）
                            const timeEl = item.querySelector(".s-p .s2");  // 发布时间

                            return {
                                title: titleEl ? titleEl.innerText.trim() : "No Title",
                                link: titleEl ? titleEl.href : "",
                                abstract: abstractEl ? abstractEl.innerText.trim() : "No Abstract",
                                source: sourceEl ? sourceEl.innerText.trim() : "Unknown Source",
                                time: timeEl ? timeEl.innerText.trim() : "Unknown Time"
                            };
                        });
                    }""")

                    # 去重：避免分页时重复抓取（如第一页和第二页有重复结果）
                    new_results = []
                    existing_links = {res["link"] for res in results}
                    for res in current_page_results:
                        if (
                            res["link"] not in existing_links
                            and res["title"] != "No Title"
                        ):
                            new_results.append(res)
                            existing_links.add(res["link"])

                    # 合并结果
                    results.extend(new_results)
                    logger.info(
                        f"Page {current_page} extracted {len(new_results)} new results"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to extract page {current_page} results: {str(e)}",
                        exc_info=True,
                    )
                    current_page += 1
                    continue

                # 7. 翻页逻辑（判断是否需要继续翻页）
                if len(results) >= max_results:
                    logger.info(
                        f"Reached target results ({len(results)}/{max_results}), stop crawling"
                    )
                    break

                # 定位下一页按钮（搜狗微信搜索的下一页ID为"sogou_next"）
                next_page_btn = page.locator("a#sogou_next")
                if (
                    await next_page_btn.is_visible(timeout=5000)
                    and await next_page_btn.is_enabled()
                ):
                    logger.info(f"Navigating to page {current_page + 1}")
                    # 滚动到下一页按钮（避免按钮在视窗外不可点击）
                    await next_page_btn.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    await next_page_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    await asyncio.sleep(random.uniform(1.5, 2.5))  # 给新页加载时间
                    current_page += 1
                else:
                    logger.warning(
                        f"No next page found (page {current_page}), stop crawling"
                    )
                    break
            # 截取目标数量的结果（避免超出max_results）
            results = results[:max_results]
            serp_success = True

        except Exception as e:
            logger.error(f"Fatal error during crawling: {str(e)}", exc_info=True)
            results = []  # 爬取失败时返回空列表
        finally:
            # 确保浏览器关闭（避免资源泄漏）
            if "browser" in locals() and browser.is_connected():
                await context.close()
                await browser.close()
            logger.info(f"Crawling finished. Final results count: {len(results)}")

    # 8. 返回结果（统一格式）
    return json.dumps(results[:max_results], ensure_ascii=False)


WEB_SEARCH_TOOL_DESCRIPTION = """
A search engine optimized for comprehensive, accurate, and trusted results.
Usage:
- The queries parameter is the list of search query

Examples:
- Search for "Python" on the web: `web_search(queries=["Python"])`
"""


async def summary(results, context, model_name):
    logger.info("===>开始压缩网页内容<===")
    _summarize_tasks = []
    for res in results:
        _summarize_input = SuperState(messages=[HumanMessage(res["text"])])
        tmp = {**context, "model": model_name}
        _summarize_context = SuperContext(**tmp)
        _summarize_tasks.append(
            await webpage_summarize_agent.ainvoke(
                _summarize_input, context=_summarize_context
            )
        )

    _summarize_tasks_output = await asyncio.gather(*_summarize_tasks)

    for i, _out in enumerate(_summarize_tasks_output):
        _data = _out.get("data")
        _summarize_output = ""
        if _data:
            _summarize_output = _data.get("result")
        if _summarize_output:
            results[i]["text"] = _summarize_output
        else:
            results[i]["text"] = truncate_if_too_long(results[i]["text"])


@tool("web_search", description=WEB_SEARCH_TOOL_DESCRIPTION)
async def web_search(
    queries: list[str], runtime: ToolRuntime[SuperContext, SuperState]
) -> str:
    try:
        logger.info(f"开始网络检索：检索词: {queries}")

        # 获取搜索结果
        search_tasks = []
        for query in queries:
            search_tasks.append(web_serp.arun({"query": query, "max_results": 2}))
        search_results = await asyncio.gather(*search_tasks)

        unique_results = {}
        for i, response in enumerate(search_results):
            serp_list = json.loads(response)
            for result in serp_list:
                url = result["link"]
                if url not in unique_results:
                    unique_results[url] = {**result, "query": queries[i]}

        logger.info(f"Search results size: {len(unique_results)}")

        # 获取网站内容
        crawl_tasks = []
        urls = []
        for url, result in unique_results.items():
            crawl_tasks.append(web_crawl.arun({"url": url}))
            urls.append(url)

        crawl_results = await asyncio.gather(*crawl_tasks)

        results = []
        for url, result in zip(urls, crawl_results):
            text = clean_markdown_links(result)
            unique_results[url]["content"] = text
            results.append(
                {
                    "url": url,
                    "text": text,
                    "title": unique_results[url]["title"],
                    "source": unique_results[url]["source"],
                }
            )

        # 这里加入summarize 因为从网络上爬取的内容太乱了
        models = runtime.context.get("models")
        summarize_model = None
        if models and models.get("summarize"):
            summarize_model = models.get("summarize")

        if summarize_model:
            await summary(results, runtime.context, summarize_model)

        logger.info(f"网络检索完成，检索结果数量: {len(results)}")

        return json.dumps(results, ensure_ascii=False)

    except Exception as e:
        return f"Error: Unexpected error listing directory: {type(e).__name__}: {e}"


@tool("web_search", description=WEB_SEARCH_TOOL_DESCRIPTION)
async def wechat_search(
    queries: list[str], runtime: ToolRuntime[SuperContext, SuperState]
) -> str:
    try:
        logger.info(f"开始网络检索：检索词: {queries}")

        # 获取搜索结果
        search_tasks = []
        for query in queries:
            search_tasks.append(wechat_serp.arun({"query": query, "max_results": 3}))
        search_results = await asyncio.gather(*search_tasks)

        unique_results = {}
        for response in search_results:
            for result in response["result"]:
                url = result["link"]
                if url not in unique_results:
                    unique_results[url] = {**result, "query": response["query"]}

        logger.info(f"Search results size: {len(unique_results)}")

        # 获取网站内容
        crawl_tasks = []
        urls = []
        for url, result in unique_results.items():
            crawl_tasks.append(wechat_crawl.arun({"url": url}))
            urls.append(url)

        crawl_results = await asyncio.gather(*crawl_tasks)

        results = []
        for url, result in zip(urls, crawl_results):
            text = clean_markdown_links(result)
            unique_results[url]["content"] = text
            results.append(
                {
                    "url": url,
                    "text": text,
                    "title": unique_results[url]["title"],
                    "source": unique_results[url]["source"],
                }
            )

        # 这里加入summarize 因为从网络上爬取的内容太乱了
        models = runtime.context.get("models")
        summarize_model = None
        if models and models.get("summarize"):
            summarize_model = models.get("summarize")

        if summarize_model:
            await summary(results, runtime.context, summarize_model)

        logger.info(f"网络检索完成，检索结果数量: {len(unique_results)}")
        return json.dumps(unique_results, ensure_ascii=False)

    except Exception as e:
        return f"Error: Unexpected error listing directory: {type(e).__name__}: {e}"
