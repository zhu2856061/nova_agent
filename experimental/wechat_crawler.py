# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from datetime import datetime
from typing import Optional, Type

from langchain_core.tools import BaseTool
from markdownify import markdownify
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from pydantic import BaseModel, Field

from nova.utils.url_fetcher import SogouUrlFetcher

logger = logging.getLogger(__name__)


class CrawlWechatToolInput(BaseModel):
    """Input schema for the CrawlTool."""

    url: str = Field(description="The URL to crawl")


class CrawlWechatTool(BaseTool):
    name: str = "wechat_crawler"
    description: str = (
        "A tool that crawls wechat websites and returns the content in markdown format"
    )
    args_schema: Type[BaseModel] = CrawlWechatToolInput

    async def _arun(self, url: str):
        """
        获取微信文章内容并转换为Markdown格式

        Args:
            url: 微信文章链接

        Returns:
            转换后的Markdown格式内容
        """
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

        # 控制请求频率，避免过快请求
        self._control_request_rate(last_request_time, MIN_REQUEST_INTERVAL)

        # 随机选择用户代理
        user_agent = random.choice(USER_AGENTS)
        url = SogouUrlFetcher().get_real_url(url)
        logger.info(f"请求链接: {url}")

        if not url:
            logger.warning(f"无法获取真实链接: {url}")
            return

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
                await self._inject_stealth_scripts(context)

                # 模拟真实用户的本地存储和cookie
                await self._setup_fake_storage(context)

                page = await context.new_page()

                # 先访问微信首页，建立正常访问流程
                # await self._pre_visit(page)

                # 导航到文章页面，使用随机等待策略
                logger.info(f"Navigating to article: {url}")
                await page.goto(url)

                # 随机等待页面加载，模拟用户等待
                await self._random_delay(1000, 3000)

                # 模拟用户滚动页面
                await self._simulate_scrolling(page)

                # 等待页面完全加载
                await page.wait_for_load_state("domcontentloaded", timeout=10000)

                # 再次随机滚动
                await self._simulate_scrolling(page)
                await self._random_delay(1000, 2000)

                # 检查是否触发反爬
                if "wechat.sogou.com/antispider" in page.url or "verify" in page.url:
                    logger.warning("⚠️ Anti-spider page detected when accessing article")
                    return f"# 提取文章内容失败，进入验证码网页了\n\n原文链接: {url}"

                # 提取文章内容
                title = await self._extract_title(page)
                metadata = await self._extract_metadata(page)
                content_html = await self._extract_content(page)
                content_md = markdownify(content_html)
                content_md = self._remove_svg_data(content_md + "\n")

                # 组合完整的Markdown内容
                # full_md = f"# {title}\n\n"
                # full_md += f"**来源**: {metadata.get('source', '未知')}\n"
                # full_md += f"**发布时间**: {metadata.get('publish_time', '未知')}\n"
                # full_md += f"**原文链接**: {url}\n\n"
                # full_md += "---\n\n"
                # full_md += content_md
                full_md = {
                    "title": title,
                    "content": content_md,
                    "url": url,
                    "source": metadata.get("source", "未知"),
                    "publish_time": metadata.get("publish_time", "未知"),
                }

                # 更新最后请求时间
                last_request_time = time.time()
                return full_md

            except Exception as e:
                logger.error(
                    f"Error extracting article content: {str(e)}", exc_info=True
                )
                return f"# 提取文章内容失败\n\n错误信息: {str(e)}\n\n原文链接: {url}"
            finally:
                if context:
                    await context.close()
                if browser and browser.is_connected():
                    await browser.close()

    async def _inject_stealth_scripts(self, context: BrowserContext):
        """注入反指纹脚本，修改浏览器关键标识"""
        # 脚本1：隐藏navigator.webdriver（核心）
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        # 脚本2：修改Canvas指纹（避免自动化工具的固定Canvas值）
        await context.add_init_script("""
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {
                const result = originalToDataURL.apply(this, arguments);
                // 对结果添加微小随机扰动（不影响显示，仅改变指纹）
                return result.replace('data:image/png;base64,', 'data:image/png;base64,' + Math.random().toString(36).substr(2, 5));
            };
        """)

        # 脚本3：修改WebGL指纹（模拟不同显卡的渲染差异）
        await context.add_init_script("""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) { // UNMASKED_VENDOR_WEBGL
                    return ['Intel Inc.', 'NVIDIA Corporation', 'AMD'].sort(() => 0.5 - Math.random())[0];
                }
                if (parameter === 37446) { // UNMASKED_RENDERER_WEBGL
                    return ['Intel Iris OpenGL Engine', 'NVIDIA GeForce GTX 1050', 'AMD Radeon Pro 555X'].sort(() => 0.5 - Math.random())[0];
                }
                return getParameter.apply(this, arguments);
            };
        """)

        # 脚本4：删除window.navigator中的自动化标识
        await context.add_init_script("""
            delete window.navigator.webdriver;
            delete window.navigator.plugins['Chrome PDF Viewer']; // 避免插件列表异常
        """)

    def _control_request_rate(self, last_request_time, MIN_REQUEST_INTERVAL):
        """控制请求频率，确保请求间隔足够长"""
        current_time = time.time()
        elapsed = current_time - last_request_time

        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed + random.uniform(0, 2)
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

    async def _random_delay(self, min_ms: int, max_ms: int):
        """随机延迟，单位毫秒"""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def _pre_visit(self, page: Page):
        """访问前置页面，模拟正常浏览流程"""
        # 先访问微信首页
        await page.goto("https://wechat.qq.com/", wait_until="networkidle")
        await self._random_delay(1000, 3000)

        # 随机点击几个元素，模拟用户行为
        try:
            nav_items = page.locator("a[href]")
            count = await nav_items.count()
            if count > 0:
                # 随机点击1-2个导航链接
                for _ in range(random.randint(1, 2)):
                    index = random.randint(0, min(count - 1, 10))
                    await nav_items.nth(index).click()
                    await self._random_delay(1000, 3000)
                    await page.go_back()
                    await self._random_delay(500, 1500)
        except Exception as e:
            logger.warning(f"Pre-visit actions failed: {str(e)}")

    async def _simulate_scrolling(self, page: Page):
        """模拟用户滚动行为"""
        # 随机滚动几次

        for _ in range(random.randint(2, 5)):
            # 随机滚动到页面的某个位置
            scroll_position = random.randint(0, 800)
            await page.evaluate(f"window.scrollTo(0, {scroll_position})")
            await self._random_delay(500, 1500)

        # 最后滚动到顶部
        await page.evaluate("window.scrollTo(0, 0)")
        await self._random_delay(500, 1000)

    async def _setup_fake_storage(self, context: BrowserContext):
        """设置模拟的本地存储和Cookie，增加真实性"""
        # 设置一些常见的Cookie
        cookies = [
            {
                "name": "wxuin",
                "value": str(random.randint(1000000000, 9999999999)),
                "domain": ".wechat.qq.com",
                "path": "/",
                "expires": int(time.time()) + 3600 * 24 * 7,
            },
            {
                "name": "devicetype",
                "value": f"windows-{random.randint(1000, 9999)}",
                "domain": ".wechat.qq.com",
                "path": "/",
                "expires": int(time.time()) + 3600 * 24 * 7,
            },
        ]
        await context.add_cookies(cookies)  # type: ignore

        # 设置一些本地存储
        await context.add_init_script(
            """
            () => {
                // 模拟用户已经访问过的记录
                localStorage.setItem('last_visit', '"""
            + datetime.now().isoformat()
            + """');
                localStorage.setItem('view_count', '"""
            + str(random.randint(10, 100))
            + """');
            }
        """
        )

    async def _extract_title(self, page: Page) -> str:
        """提取文章标题"""
        try:
            # 微信文章常见的标题选择器，增加多个备选
            title_selectors = [
                "h1#activity-name",
                ".rich_media_title",
                ".title",
                "header h1",
            ]

            for selector in title_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    title = await page.locator(selector).text_content()
                    if title and title.strip():
                        return title.strip()
                except Exception:
                    continue

            # 备选方案，获取页面标题
            page_title = await page.title()
            return page_title.strip() if page_title else "未知标题"
        except Exception as e:
            logger.warning(f"Error extracting title: {str(e)}")
            return "未知标题"

    async def _extract_metadata(self, page: Page) -> dict:
        """提取文章元数据（来源、发布时间等）"""
        metadata = {}
        try:
            # 提取来源（公众号名称）
            source_selectors = [
                ".rich_media_meta_list .rich_media_meta_nickname",
                ".author",
                ".source",
            ]

            for selector in source_selectors:
                if await page.locator(selector).is_visible():
                    source = await page.locator(selector).text_content()
                    if source and source.strip():
                        metadata["source"] = source.strip()
                        break
            else:
                metadata["source"] = "未知来源"

            # 提取发布时间
            time_selectors = [
                "#publish_time",
                ".rich_media_meta .rich_media_meta_text",
            ]

            for selector in time_selectors:
                if await page.locator(selector).is_visible():
                    publish_time = await page.locator(selector).text_content()
                    if publish_time and publish_time.strip():
                        metadata["publish_time"] = publish_time.strip()
                        break
            else:
                metadata["publish_time"] = "未知时间"

        except Exception as e:
            logger.warning(f"Error extracting metadata: {str(e)}")

        return metadata

    def _remove_svg_data(self, text):
        # 正则表达式模式：匹配所有Markdown格式的SVG图片
        # 特点：以![](./data:image/svg+xml,开头，包含任意字符，直到)结束
        svg_pattern = r"!\[.*?\]\(data:image/svg\+xml,.*?\n"
        cleaned_text = re.sub(svg_pattern, "", text)

        # 特点：以![](https,开头，包含任意字符，直到)结束
        img_pattern = r"!\[图片\]\(https://mmbiz\.qpic\.cn/.*?\)"
        cleaned_text = re.sub(img_pattern, "", cleaned_text)

        # 可选：清除替换后可能产生的空行
        cleaned_text = re.sub(r"\n\s*\n", "\n\n", cleaned_text).strip()

        return cleaned_text

    async def _extract_content(self, page: Page) -> str:
        """提取文章正文HTML"""
        try:
            # 微信文章常见的内容选择器，增加多个备选
            content_selectors = [
                "#js_content",
                ".rich_media_content",
                ".article_content",
                ".content",
            ]

            content_html = None
            for selector in content_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    content_html = await page.locator(selector).inner_html()
                    if content_html:
                        break
                except Exception:
                    continue

            if not content_html:
                return "<p>无法找到文章内容区域</p>"

            # 清理不需要的元素（广告、推荐等）
            clean_html = await page.evaluate(
                """(html) => {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = html;
                
                // 移除脚本和样式
                const scripts = tempDiv.querySelectorAll('script, style, noscript');
                scripts.forEach(el => el.remove());
                
                // 移除广告和推荐内容
                const ads = tempDiv.querySelectorAll(
                    '.ads_box, .recommend_box, .copyright_box, .advertisement, ' +
                    '.related_articles, .like_area, .share_area, .comment_area'
                );
                ads.forEach(el => el.remove());
                
                // 移除空标签
                const emptyTags = tempDiv.querySelectorAll('p:empty, div:empty, span:empty');
                emptyTags.forEach(el => el.remove());
                
                return tempDiv.innerHTML;
            }""",
                content_html,
            )

            return clean_html
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return f"<p>无法提取文章内容: {str(e)}</p>"

    # 同步版本的文章提取方法
    def _run(self, url: str):
        """Synchronous wrapper for the async crawl function."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return loop.create_task(self._arun(url))
            else:
                return loop.run_until_complete(self._arun(url))
        except RuntimeError:
            return asyncio.run(self._arun(url))
