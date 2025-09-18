# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import logging
import random
from typing import Optional, Type

from langchain_core.tools import BaseTool
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SerpWechatToolInput(BaseModel):
    """Input schema for the SerpTool."""

    query: str = Field(description="The query to search for")
    max_results: Optional[int] = Field(
        default=5, description="Maximum number of results to return"
    )


class SerpWechatTool(BaseTool):
    name: str = "serp_wechat_tool"
    description: str = "A tool that searches the web and returns the top results"
    args_schema: Type[BaseModel] = SerpWechatToolInput

    async def _arun(self, query: str, max_results: int):
        # 1. 配置浏览器参数（增强反爬）
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        results = []  # 存储最终结果
        current_page = 1  # 当前页码
        max_pages = 10  # 最大翻页次数（防止无限循环）
        serp_success = False  # 爬取状态标记
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
                        raise Exception(
                            "Submit button remains disabled, cannot proceed"
                        )

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
        return {
            "query": query,
            "max_results_requested": max_results,
            "results": results,
            "serp_success": serp_success,
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
serp_wechat_tool = SerpWechatTool()
