# -*- coding: utf-8 -*-
# @Time   : 2025/09/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from playwright.async_api import BrowserContext, Page

# 配置日志
logger = logging.getLogger(__name__)


class SogouCookieManager:
    """Cookie池管理类，负责Cookie的生成、验证和更新"""

    def __init__(self, cookie_expiry_hours: int = 24):
        self.cookie_pool = []  # 存储格式: (cookies_dict, create_time)
        self.expiry_hours = cookie_expiry_hours
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Edg/137.0.0.0",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.6723.71 Mobile Safari/537.36",
        ]

        # 初始化Cookie池
        self._init_cookie_pool(min_size=2)

    def _init_cookie_pool(self, min_size: int):
        """初始化Cookie池，确保有足够的有效Cookie"""
        logger.info(f"初始化Cookie池，目标数量: {min_size}")
        while len(self.cookie_pool) < min_size:
            self._add_new_cookie()
            time.sleep(random.uniform(2, 4))  # 避免集中创建

    def _generate_base_cookies(self) -> dict:
        """生成基础Cookie信息"""
        timestamp = int(time.time() * 1000)
        suid = hashlib.md5(str(timestamp).encode()).hexdigest().upper()

        return {
            "ABTEST": f"7|{timestamp}|v1",
            "SUID": suid,
            "IPLOC": f"CN{random.randint(1100, 6500)}",  # 模拟不同地区
            "SUV": f"{random.randint(10000000, 99999999)}{timestamp}",
            "SNUID": hashlib.md5(str(random.random()).encode()).hexdigest().upper(),
        }

    def _add_new_cookie(self) -> bool:
        """创建并验证新Cookie，成功则加入池"""
        try:
            session = requests.Session()
            headers = self._get_random_headers()

            # 访问主页获取完整Cookie
            session.get(
                "https://weixin.sogou.com/",
                headers=headers,
                timeout=10,
                allow_redirects=True,
            )

            # 验证Cookie有效性
            test_url = "https://weixin.sogou.com/weixin?type=2&query=科技"
            response = session.get(test_url, headers=headers, timeout=10)

            if "antispider" not in response.text and response.status_code == 200:
                # 转换为Cookie字典
                cookie_dict = {cookie.name: cookie.value for cookie in session.cookies}
                self.cookie_pool.append((cookie_dict, datetime.now()))
                logger.info(f"新Cookie添加成功，当前池大小: {len(self.cookie_pool)}")
                return True
            else:
                logger.warning("新Cookie验证失败")
                return False

        except Exception as e:
            logger.error(f"创建Cookie失败: {str(e)}")
            return False

    def _get_random_headers(self) -> dict:
        """获取随机请求头"""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": random.choice(self.user_agents),
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }

    def get_valid_cookie(self) -> Optional[dict]:
        """获取一个有效的Cookie，移除过期的"""
        # 清理过期Cookie
        now = datetime.now()
        self.cookie_pool = [
            (cookie, create_time)
            for cookie, create_time in self.cookie_pool
            if now - create_time < timedelta(hours=self.expiry_hours)
        ]

        # 如果Cookie不足，补充新的
        if len(self.cookie_pool) < 2:
            logger.info("Cookie池数量不足，补充新Cookie")
            self._add_new_cookie()

        return random.choice(self.cookie_pool)[0] if self.cookie_pool else None


class SogouUrlFetcher:
    """搜狗微信链接解析器"""

    def __init__(self):
        self.cookie_manager = SogouCookieManager()
        self.request_interval = (2, 5)  # 请求间隔范围(秒)
        self.last_request_time = 0
        self.max_retries = 3

    def _wait_for_rate_limit(self):
        """控制请求频率，避免过快"""
        elapsed = time.time() - self.last_request_time
        required_wait = random.uniform(*self.request_interval) - elapsed

        if required_wait > 0:
            time.sleep(required_wait)
        self.last_request_time = time.time()

    def get_real_url(self, sogou_url: str) -> str:
        """获取真实微信文章链接"""
        if not sogou_url:
            return ""

        for retry in range(self.max_retries):
            try:
                self._wait_for_rate_limit()

                # 获取随机Cookie和 headers
                cookie_dict = self.cookie_manager.get_valid_cookie()
                if not cookie_dict:
                    logger.error("没有可用的Cookie")
                    time.sleep(5)
                    continue

                headers = self.cookie_manager._get_random_headers()
                headers["Cookie"] = "; ".join(
                    [f"{k}={v}" for k, v in cookie_dict.items()]
                )

                # 发送请求
                session = requests.Session()
                response = session.get(
                    sogou_url, headers=headers, timeout=15, allow_redirects=True
                )

                # 检查是否触发反爬
                if "antispider" in response.text or "验证码" in response.text:
                    logger.warning(f"第{retry + 1}次尝试触发反爬，更换Cookie")
                    # 移除当前可能已被标记的Cookie
                    if cookie_dict in [c for c, _ in self.cookie_manager.cookie_pool]:
                        self.cookie_manager.cookie_pool = [
                            (c, t)
                            for c, t in self.cookie_manager.cookie_pool
                            if c != cookie_dict
                        ]
                    time.sleep(random.uniform(5, 8))
                    continue

                # 检查是否直接跳转
                if "mp.weixin.qq.com" in response.url:
                    return response.url

                # 解析页面中的链接
                script_content = response.text
                url_parts = []
                start_index = 0

                while True:
                    part_start = script_content.find("url += '", start_index)
                    if part_start == -1:
                        break
                    part_end = script_content.find("'", part_start + len("url += '"))
                    if part_end == -1:
                        break
                    url_parts.append(
                        script_content[part_start + len("url += '") : part_end]
                    )
                    start_index = part_end + 1

                full_url = "".join(url_parts).replace("@", "")
                if full_url:
                    # 补全URL格式
                    if full_url.startswith("//"):
                        return f"https:{full_url}"
                    elif not full_url.startswith("http"):
                        return f"https://{full_url}"
                    return full_url

            except Exception as e:
                logger.error(f"第{retry + 1}次尝试失败: {str(e)}")
                time.sleep(random.uniform(3, 6))

        logger.error(f"多次尝试后仍无法获取链接: {sogou_url}")
        return ""

    async def inject_stealth_scripts(self, context: BrowserContext):
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

    def control_request_rate(self, last_request_time, MIN_REQUEST_INTERVAL):
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

    async def pre_visit(self, page: Page):
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

    async def simulate_scrolling(self, page: Page):
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

    async def setup_fake_storage(self, context: BrowserContext):
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

    async def extract_title(self, page: Page) -> str:
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

    async def extract_metadata(self, page: Page) -> dict:
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

    def remove_svg_data(self, text):
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

    async def extract_content(self, page: Page) -> str:
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
