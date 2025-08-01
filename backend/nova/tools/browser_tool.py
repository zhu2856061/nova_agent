# -*- coding: utf-8 -*-
# @Time   : 2025/01/27 15:30
# @Author : Assistant
# @Moto   : 浏览器自动化工具，支持网页导航、元素交互、内容提取等功能

import asyncio
import json
import logging
import platform
import sys
from typing import Optional

from langchain_core.tools import tool
from pydantic import Field

# 设置Windows环境下的异步事件循环策略
if platform.system() == "Windows":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception as e:
        logging.warning(f"设置Windows事件循环策略失败: {e}")

logger = logging.getLogger(__name__)

# 浏览器工具描述
_BROWSER_DESCRIPTION = """
与网页浏览器交互，执行各种操作，如导航、元素交互、内容提取和标签页管理。
使用此工具时，请优先访问中国国内的网站。此工具提供全面的浏览器自动化功能：

导航功能：
- 'go_to_url'：在当前标签页访问指定URL
- 'go_back'：返回上一页
- 'refresh'：刷新当前页面
- 'web_search'：在当前标签页中搜索查询内容

元素交互：
- 'click_element'：通过索引点击元素
- 'input_text'：在表单元素中输入文本
- 'scroll_down'/'scroll_up'：滚动页面
- 'scroll_to_text'：滚动到指定文本
- 'send_keys'：发送特殊键或快捷键

内容提取：
- 'extract_content'：提取页面内容以获取特定信息

标签页管理：
- 'switch_tab'：切换到特定标签页
- 'open_tab'：打开带有URL的新标签页
- 'close_tab'：关闭当前标签页

实用工具：
- 'wait'：等待指定的秒数
- 'get_state'：获取当前浏览器状态
"""

# 统一的浏览器配置
BROWSER_CONFIGS = [
    {
        "type": "chromium",
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
        ],
    },
    {
        "type": "chromium",
        "args": ["--no-sandbox"],  # 最简配置
    },
    {"type": "firefox", "args": []},
]


async def wait_for_page_load(page, timeout=15000):
    """统一的页面加载等待逻辑"""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception as e:
        logger.warning(f"页面加载等待超时，但继续执行: {e}")


async def create_browser_instance():
    """创建浏览器实例"""
    try:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        logger.debug("🚀 Playwright实例已创建")

        for config in BROWSER_CONFIGS:
            try:
                browser_type = config["type"]
                args = config["args"]
                logger.debug(f"🚀 尝试启动 {browser_type} 浏览器")

                if browser_type == "chromium":
                    browser = await playwright.chromium.launch(headless=True, args=args)
                elif browser_type == "firefox":
                    browser = await playwright.firefox.launch(
                        headless=True,
                        firefox_user_prefs={
                            "media.navigator.permission.disabled": True
                        },
                    )

                # 创建上下文和页面
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = await context.new_page()

                # 设置超时
                page.set_default_timeout(30000)
                page.set_default_navigation_timeout(30000)

                logger.debug(f"✅ {browser_type} 浏览器实例创建成功")
                return playwright, browser, context, page

            except Exception as e:
                logger.debug(f"❌ 启动 {browser_type} 失败: {e}")
                continue

        raise RuntimeError("无法启动任何浏览器")

    except ImportError:
        raise RuntimeError(
            "Playwright未安装，请运行: pip install playwright && playwright install"
        )


async def cleanup_browser_resources(
    playwright=None, browser=None, context=None, page=None
):
    """统一的资源清理函数"""
    for resource, name in [
        (page, "Page"),
        (context, "Context"),
        (browser, "Browser"),
        (playwright, "Playwright"),
    ]:
        try:
            if (
                resource
                and hasattr(resource, "_impl_obj")
                and resource._impl_obj is not None
            ):
                if name == "Playwright":
                    await resource.stop()
                else:
                    await resource.close()
                logger.debug(f"✅ {name}已清理")
        except Exception as e:
            logger.debug(f"清理{name}失败: {e}")


async def with_browser_instance(operation_func):
    """使用浏览器实例执行操作的包装器 - 简化版本"""
    playwright = browser = context = page = None

    try:
        playwright, browser, context, page = await create_browser_instance()
        result = await operation_func(page, context, browser)
        return result

    except Exception as e:
        logger.error(f"浏览器操作失败: {e}")
        return f"执行失败: {str(e)}"

    finally:
        await cleanup_browser_resources(playwright, browser, context, page)


def run_sync_async(coro):
    """同步运行异步协程"""
    try:
        if sys.meta_path is None:
            return "Python正在关闭，无法执行浏览器操作"

        async def coro_with_timeout():
            try:
                return await asyncio.wait_for(coro, timeout=45.0)
            except asyncio.TimeoutError:
                return "执行失败: 浏览器操作超时"
            except Exception as e:
                return f"执行失败: {str(e)}"

        # 检查是否有运行中的事件循环
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is not None:
            # 在新线程中运行
            import concurrent.futures

            def run_in_thread():
                try:
                    if platform.system() == "Windows":
                        asyncio.set_event_loop_policy(
                            asyncio.WindowsProactorEventLoopPolicy()
                        )

                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro_with_timeout())
                    finally:
                        try:
                            pending = asyncio.all_tasks(new_loop)
                            for task in pending:
                                task.cancel()
                            if pending:
                                new_loop.run_until_complete(
                                    asyncio.gather(*pending, return_exceptions=True)
                                )
                            new_loop.close()
                        except Exception:
                            pass
                        finally:
                            asyncio.set_event_loop(None)
                except Exception as e:
                    return f"执行失败: {str(e)}"

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                try:
                    return future.result(timeout=50)
                except concurrent.futures.TimeoutError:
                    return "执行失败: 操作超时"
        else:
            # 直接运行
            if platform.system() == "Windows":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            return asyncio.run(coro_with_timeout())

    except Exception as e:
        logger.error(f"执行异步协程失败: {e}")
        return f"执行失败: {str(e)}"


@tool(
    "browser_navigate_tool",
    description="浏览器导航工具：访问URL、返回、刷新页面等操作",
)
def browser_navigate_tool(
    action: str = Field(..., description="导航操作：go_to_url, go_back, refresh"),
    url: Optional[str] = Field(
        default=None, description="要访问的URL（仅go_to_url需要）"
    ),
):
    """执行浏览器导航操作"""

    async def _execute():
        async def operation(page, context, browser):
            if action == "go_to_url":
                if not url:
                    return "错误: go_to_url操作需要提供URL"
                await page.goto(url, timeout=30000)
                await wait_for_page_load(page)
                logger.info(f"✅ 成功导航到: {url}")
                return f"成功导航到: {url}"

            elif action == "go_back":
                await page.go_back(timeout=30000)
                await wait_for_page_load(page)
                logger.info("✅ 成功返回上一页")
                return "成功返回上一页"

            elif action == "refresh":
                await page.reload(timeout=30000)
                await wait_for_page_load(page)
                logger.info("✅ 成功刷新页面")
                return "成功刷新页面"

            else:
                return f"错误: 不支持的导航操作: {action}"

        return await with_browser_instance(operation)

    return run_sync_async(_execute())


@tool(
    "browser_interact_tool",
    description="浏览器交互工具：点击元素、输入文本、滚动、发送按键等",
)
def browser_interact_tool(
    action: str = Field(
        ...,
        description="交互操作：click_element, input_text, scroll_down, scroll_up, scroll_to_text, send_keys",
    ),
    selector: Optional[str] = Field(
        default=None, description="CSS选择器或XPath（click_element, input_text需要）"
    ),
    text: Optional[str] = Field(
        default=None, description="文本内容（input_text, scroll_to_text需要）"
    ),
    scroll_amount: Optional[int] = Field(
        default=None, description="滚动像素数（scroll_down, scroll_up需要）"
    ),
    keys: Optional[str] = Field(default=None, description="按键（send_keys需要）"),
):
    """执行浏览器交互操作"""

    async def _execute():
        async def operation(page, context, browser):
            if action == "click_element":
                if not selector:
                    return "错误: click_element操作需要提供选择器"
                await page.click(selector, timeout=30000)
                logger.info(f"✅ 成功点击元素: {selector}")
                return f"成功点击元素: {selector}"

            elif action == "input_text":
                if not selector or not text:
                    return "错误: input_text操作需要提供选择器和文本"
                await page.fill(selector, text, timeout=30000)
                logger.info(f"✅ 成功在元素{selector}输入文本: {text}")
                return f"成功在元素{selector}输入文本: {text}"

            elif action in ["scroll_down", "scroll_up"]:
                direction = 1 if action == "scroll_down" else -1
                amount = scroll_amount or 500
                await page.evaluate(f"window.scrollBy(0, {direction * amount})")
                logger.info(
                    f"✅ 成功滚动{'下' if direction > 0 else '上'}: {amount}像素"
                )
                return f"成功滚动{'下' if direction > 0 else '上'}: {amount}像素"

            elif action == "scroll_to_text":
                if not text:
                    return "错误: scroll_to_text操作需要提供文本"
                try:
                    await page.get_by_text(
                        text, exact=False
                    ).scroll_into_view_if_needed(timeout=30000)
                    logger.info(f"✅ 成功滚动到文本: {text}")
                    return f"成功滚动到文本: {text}"
                except Exception as e:
                    return f"滚动到文本失败: {str(e)}"

            elif action == "send_keys":
                if not keys:
                    return "错误: send_keys操作需要提供按键"
                await page.keyboard.press(keys)
                logger.info(f"✅ 成功发送按键: {keys}")
                return f"成功发送按键: {keys}"

            else:
                return f"错误: 不支持的交互操作: {action}"

        return await with_browser_instance(operation)

    return run_sync_async(_execute())


@tool(
    "browser_extract_tool",
    description="浏览器内容提取工具：提取页面内容、获取页面状态等",
)
def browser_extract_tool(
    action: str = Field(..., description="提取操作：extract_content, get_state"),
    goal: Optional[str] = Field(
        default=None, description="提取目标（extract_content需要）"
    ),
):
    """执行浏览器内容提取操作"""

    async def _execute():
        async def operation(page, context, browser):
            if action == "extract_content":
                if not goal:
                    return "错误: extract_content操作需要提供提取目标"

                # 获取页面内容
                content = await page.content()

                # 尝试转换为markdown
                try:
                    import markdownify

                    content = markdownify.markdownify(content)
                except ImportError:
                    # 简单的HTML清理
                    import re

                    content = re.sub(r"<[^>]+>", "", content)
                    content = re.sub(r"\s+", " ", content).strip()

                # 限制内容长度
                max_length = 3000
                content = (
                    content[:max_length] + "..."
                    if len(content) > max_length
                    else content
                )

                result = f"提取目标: {goal}\n\n页面内容:\n{content}"
                logger.info(f"✅ 成功提取内容，目标: {goal}")
                return result

            elif action == "get_state":
                url = page.url
                title = await page.title()

                # 获取页面文本内容
                text_content = await page.text_content("body")
                text_content = (
                    text_content[:1000] + "..."
                    if len(text_content) > 1000
                    else text_content
                )

                state_info = {
                    "url": url,
                    "title": title,
                    "content_preview": text_content,
                    "help": "使用CSS选择器或XPath来定位元素，例如：'button', '#id', '.class', '//button[contains(text(), \"text\")]'",
                }

                result = f"当前浏览器状态:\n{json.dumps(state_info, indent=2, ensure_ascii=False)}"
                logger.info("✅ 成功获取浏览器状态")
                return result

            else:
                return f"错误: 不支持的提取操作: {action}"

        return await with_browser_instance(operation)

    return run_sync_async(_execute())


@tool(
    "browser_tab_tool",
    description="浏览器标签页管理工具：切换、打开、关闭标签页",
)
def browser_tab_tool(
    action: str = Field(..., description="标签页操作：switch_tab, open_tab, close_tab"),
    tab_index: Optional[int] = Field(
        default=None, description="标签页索引（switch_tab需要）"
    ),
    url: Optional[str] = Field(default=None, description="URL（open_tab需要）"),
):
    """执行浏览器标签页管理操作"""

    async def _execute():
        async def operation(page, context, browser):
            if action == "switch_tab":
                if tab_index is None:
                    return "错误: switch_tab操作需要提供标签页索引"
                pages = context.pages
                if tab_index < len(pages):
                    target_page = pages[tab_index]
                    await target_page.bring_to_front()
                    logger.info(f"✅ 成功切换到标签页: {tab_index}")
                    return f"成功切换到标签页: {tab_index}"
                else:
                    return f"错误: 标签页索引{tab_index}不存在"

            elif action == "open_tab":
                if not url:
                    return "错误: open_tab操作需要提供URL"
                new_page = await context.new_page()
                await new_page.goto(url, timeout=30000)
                await wait_for_page_load(new_page)
                logger.info(f"✅ 成功打开新标签页: {url}")
                return f"成功打开新标签页: {url}"

            elif action == "close_tab":
                if len(context.pages) > 1:
                    await page.close()
                    logger.info("✅ 成功关闭当前标签页")
                    return "成功关闭当前标签页"
                else:
                    return "错误: 不能关闭最后一个标签页"

            else:
                return f"错误: 不支持的标签页操作: {action}"

        return await with_browser_instance(operation)

    return run_sync_async(_execute())


@tool(
    "browser_utility_tool",
    description="浏览器实用工具：等待、搜索等",
)
def browser_utility_tool(
    action: str = Field(..., description="实用操作：wait, web_search"),
    seconds: Optional[int] = Field(default=None, description="等待秒数（wait需要）"),
    query: Optional[str] = Field(
        default=None, description="搜索查询（web_search需要）"
    ),
):
    """执行浏览器实用操作"""

    async def _execute():
        async def operation(page, context, browser):
            if action == "wait":
                seconds_to_wait = seconds or 3
                await asyncio.sleep(seconds_to_wait)
                logger.info(f"✅ 成功等待: {seconds_to_wait}秒")
                return f"成功等待: {seconds_to_wait}秒"

            elif action == "web_search":
                if not query:
                    return "错误: web_search操作需要提供搜索查询"

                # 使用百度搜索
                search_url = f"https://www.baidu.com/s?wd={query}"
                await page.goto(search_url, timeout=30000)
                await wait_for_page_load(page)
                logger.info(f"✅ 成功搜索并导航: {query}")
                return f"成功搜索: {query}，已导航到百度搜索结果页面"

            else:
                return f"错误: 不支持的实用操作: {action}"

        return await with_browser_instance(operation)

    return run_sync_async(_execute())
