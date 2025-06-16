# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
import re
from typing import List
from urllib.parse import urljoin

import requests
from langchain_core.tools import tool
from markdownify import markdownify as md
from pydantic import Field
from readabilipy import simple_json_from_html_string

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
        parts = re.split(image_pattern, self.to_markdown())

        for i, part in enumerate(parts):
            if i % 2 == 1:
                image_url = urljoin(self.url, part.strip())
                content.append({"type": "image_url", "image_url": {"url": image_url}})
            else:
                content.append({"type": "text", "text": part.strip()})

        return content


# 🛠️
@tool("crawl_tool", description="使用此工具爬网url并以markdown格式获取可读内容。")
def crawl_tool(url: str = Field(description="要爬取的url")) -> List:
    headers = {
        "Content-Type": "application/json",
        "X-Return-Format": "html",  # 为何不用自带的format -> markdown, 发现自带的效果不好，总是一大串字符串
    }
    if os.getenv("JINA_API_KEY"):
        headers["Authorization"] = f"Bearer {os.getenv('JINA_API_KEY')}"

    try:
        logger.info(f">>>>>>> [crawl_tool] input -> url: {url}")

        # response = requests.post(
        #     "https://r.jina.ai/", headers=headers, json={"url": url}
        # )
        # article = simple_json_from_html_string(response.text, use_readability=True)
        # article = Article(
        #     url=url,
        #     title=article.get("title"),
        #     html_content=article.get("content"),
        # )
        # message = article.to_message()

        message = [
            {
                "title": "天气实况与预报 - 深圳市气象局（台）",
                "url": "https://weather.sz.gov.cn/qixiangfuwu/yubaofuwu/index.html",
                "content": [
                    {
                        "type": "text",
                        "text": "# 天气实况与预报-深圳市气象局（台）\\n\\n**深圳国家基本气象站实况**\\n18:58",
                    },
                    {"type": "text", "text": "26.8\\n\\n气温 ℃"},
                    {"type": "text", "text": "东北偏北风 小于三级\\n\\n风"},
                ],
            }
        ]

        logger.info(f"<<<<<<< [crawl_tool] output -> : {message}")

        return message

    except BaseException as e:
        error_msg = f"Failed to crawl. Error: {repr(e)}"
        logger.error(error_msg)
        return [error_msg]


# 🛠️
@tool("serp_tool", description="使用此工具在web上搜索信息并返回列表")
def serp_tool(
    query: str = Field(..., description="查询搜索，获取seo。"),
) -> List:
    try:
        # headers = {
        #     "X-API-KEY": os.getenv("GOOGLE_SERPER_API_KEY"),
        #     "Content-Type": "application/json",
        # }
        # logger.info(f">>>>>>> [serp_tool] input -> query: {query}")
        # payload = json.dumps({"q": query, "num": 1})

        # response = requests.post(
        #     os.getenv("GOOGLE_SERPER_URL"),  # type: ignore
        #     headers=headers,
        #     data=payload,  # type: ignore
        #     timeout=30.0,
        # )
        # response.raise_for_status()
        # response = response.json()["organic"]
        # # 格式转换
        # response = [
        #     {
        #         "title": item["title"],
        #         "url": item["link"],
        #         "content": item["snippet"],
        #         "score": item["position"],
        #     }
        #     for item in response
        # ]

        response = [
            {
                "title": "天气实况与预报 - 深圳市气象局（台）",
                "url": "https://weather.sz.gov.cn/qixiangfuwu/yubaofuwu/index.html",
                "content": "深圳市气象局门户网站为您提供权威、及时、准确的深圳天气预警、天气预报、天气实况、台风路径、深圳气候等信息服务，为深圳及其周边城市的生产生活提供全面可靠的气象 ...",
                "score": 1,
            }
        ]
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
