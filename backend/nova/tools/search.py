# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import asyncio
import json
import logging
import os
from typing import Dict, List

import requests
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from langchain_core.tools import tool
from pydantic import Field

logger = logging.getLogger(__name__)


# 🛠️
@tool("crawl_tool", description="使用此工具爬网url并以markdown格式获取可读内容。")
def crawl_tool(url: str = Field(description="要爬取的url")) -> Dict:
    try:
        logger.info(f">>>>>>> [crawl_tool] input -> url: {url}")

        # Create a browser configuration with builtin mode
        browser_config = BrowserConfig(
            browser_mode="builtin",  # This is the key setting!
            headless=True,  # Can run headless for background operation
        )

        # Create crawler run configuration
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # Skip cache for this demo
            screenshot=True,  # Take a screenshot
            verbose=True,  # Show verbose logging
        )

        # 异步爬取网页内容
        async def fetch_content():
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=crawler_config)
                return result.markdown  # type: ignore

        # 使用 asyncio.run 调用异步任务
        markdown_content = asyncio.run(fetch_content())

        message = {
            "title": f"内容爬取自: {url}",
            "content": markdown_content,
        }

        logger.info(f"<<<<<<< [crawl_tool] output -> : {message}")

        return message

    except BaseException as e:
        error_msg = f"Failed to crawl. Error: {repr(e)}"
        logger.error(error_msg)
        return {"title": f"内容爬取自: {url}", "content": error_msg}


# 🛠️
@tool("serp_tool", description="使用此工具在web上搜索信息并返回列表")
def serp_tool(
    query: str = Field(..., description="查询搜索，获取seo。"),
) -> List:
    try:
        headers = {
            "X-API-KEY": os.getenv("GOOGLE_SERPER_API_KEY"),
            "Content-Type": "application/json",
        }
        logger.info(f">>>>>>> [serp_tool] input -> query: {query}")
        payload = json.dumps({"q": query, "num": 1})

        response = requests.post(
            os.getenv("GOOGLE_SERPER_URL"),  # type: ignore
            headers=headers,
            data=payload,  # type: ignore
            timeout=30.0,
        )
        response.raise_for_status()
        response = response.json()["organic"]
        # 格式转换
        response = [
            {
                "title": item["title"],
                "url": item["link"],
                "content": item["snippet"],
                "score": item["position"],
            }
            for item in response
        ]

        # response = [
        #     {
        #         "title": "天气实况与预报 - 深圳市气象局（台）",
        #         "url": "https://weather.sz.gov.cn/qixiangfuwu/yubaofuwu/index.html",
        #         "content": "深圳市气象局门户网站为您提供权威、及时、准确的深圳天气预警、天气预报、天气实况、台风路径、深圳气候等信息服务，为深圳及其周边城市的生产生活提供全面可靠的气象 ...",
        #         "score": 1,
        #     }
        # ]
        logger.info(f"<<<<<<< [serp_tool] output -> : {response}")
        return response

    except BaseException as e:
        error_msg = f"Failed to Serp. Error: {repr(e)}"
        logger.error(error_msg)
        return [error_msg]


# 🛠️
@tool(
    "search_tool",
    description="此工具使用提供的关键字执行搜索，并获取以markdown格式显示的信息。",
)
def search_tool(query: str = Field(description="要搜索的关键字。")) -> List:
    try:
        logger.info(f">>>>>>> [search_tool] input -> query: {query}")
        response = serp_tool.run(query)

        if response and isinstance(response, list):
            for item in response:
                if "url" in item:
                    _url = item["url"]
                    crawled_content = crawl_tool.run(_url)
                    item["content"] = crawled_content
            logger.info(f"<<<<<<< [search_tool] output -> : {response}")
            return response

        return response
    except BaseException as e:
        error_msg = f"Failed to Serp. Error: {repr(e)}"
        logger.error(error_msg)
        return [error_msg]
