# -*- coding: utf-8 -*-
# @Time   : 2025/01/27 15:30
# @Author : Assistant
# @Moto   : 增强版Web工具，整合网络搜索和内容抓取功能

import logging
from typing import List

from langchain_core.tools import tool
from pydantic import Field

logger = logging.getLogger(__name__)


@tool(
    "enhanced_web_search_tool",
    description="""执行网络搜索并返回相关结果列表。
    支持多种搜索引擎，返回标题、链接和摘要信息。
    当需要获取最新信息或搜索特定内容时使用此工具。""",
)
def enhanced_web_search_tool(
    query: str = Field(..., description="要搜索的查询关键词"),
    num_results: int = Field(default=5, description="返回的搜索结果数量，默认5个"),
    search_engine: str = Field(
        default="duckduckgo", description="使用的搜索引擎：duckduckgo, google, baidu"
    ),
):
    """
    执行Web搜索

    Args:
        query: 搜索查询
        num_results: 结果数量
        search_engine: 搜索引擎选择

    Returns:
        str: 搜索结果
    """
    logger.info(f"🔍 开始搜索: {query} (引擎: {search_engine})")

    try:
        # 使用DuckDuckGo搜索（免费且无需API密钥）
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(query, max_results=num_results)
            print("===>", search_results)
            for i, result in enumerate(search_results, 1):
                title = result.get("title", "N/A")
                href = result.get("href", "N/A")
                body = result.get("body", "N/A")

                results.append(f"{i}. **{title}**\n   链接: {href}\n   摘要: {body}\n")

        if results:
            result_text = f"搜索查询: {query}\n\n搜索结果:\n\n" + "\n".join(results)
            logger.info(f"✅ 搜索完成，找到 {len(results)} 个结果")
            return result_text
        else:
            return f"未找到与查询 '{query}' 相关的结果"

    except Exception as e:
        error_msg = f"搜索失败: {str(e)}"
        logger.error(error_msg)
        return f"错误: {error_msg}"


@tool(
    "enhanced_web_crawler_tool",
    description="""从指定URL抓取网页内容。
    可以提取网页的文本内容、标题等信息。
    适合用于获取特定网页的详细内容。""",
)
def enhanced_web_crawler_tool(
    url: str = Field(..., description="要抓取的网页URL"),
    timeout: int = Field(default=30, description="请求超时时间（秒）"),
):
    """
    抓取网页内容

    Args:
        url: 网页URL
        timeout: 超时时间

    Returns:
        str: 网页内容
    """
    logger.info(f"🌐 开始抓取网页: {url}")

    try:
        import requests
        from bs4 import BeautifulSoup

        # 发送HTTP请求
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        # 解析HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # 提取标题
        title = soup.find("title")
        title_text = title.get_text().strip() if title else "无标题"

        # 移除脚本和样式元素
        for script in soup(["script", "style"]):
            script.decompose()

        # 提取文本内容
        text = soup.get_text()

        # 清理文本
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        # 限制内容长度
        if len(text) > 5000:
            text = text[:5000] + "...[内容过长已截断]"

        result = f"网页标题: {title_text}\n\nURL: {url}\n\n内容:\n{text}"
        logger.info(f"✅ 网页抓取完成: {url}")
        return result

    except Exception as e:
        error_msg = f"抓取网页失败: {str(e)}"
        logger.error(error_msg)
        return f"错误: {error_msg}"


@tool(
    "url_validator_tool",
    description="""验证URL是否有效可访问。
    检查URL的可达性和响应状态。""",
)
def url_validator_tool(
    url: str = Field(..., description="要验证的URL"),
    timeout: int = Field(default=10, description="请求超时时间（秒）"),
):
    """
    验证URL有效性

    Args:
        url: 要验证的URL
        timeout: 超时时间

    Returns:
        str: 验证结果
    """
    logger.info(f"🔗 验证URL: {url}")

    try:
        import requests

        response = requests.head(url, timeout=timeout, allow_redirects=True)
        status_code = response.status_code

        if 200 <= status_code < 300:
            result = f"URL有效: {url} (状态码: {status_code})"
            logger.info(f"✅ URL验证成功: {url}")
        elif 300 <= status_code < 400:
            result = f"URL重定向: {url} (状态码: {status_code}) -> {response.url}"
            logger.info(f"↩️ URL重定向: {url}")
        else:
            result = f"URL访问异常: {url} (状态码: {status_code})"
            logger.warning(f"⚠️ URL状态异常: {url}")

        return result

    except Exception as e:
        error_msg = f"URL验证失败: {str(e)}"
        logger.error(error_msg)
        return f"错误: {error_msg}"


@tool(
    "extract_links_tool",
    description="""从网页中提取所有链接。
    可以提取页面中的所有超链接，便于进一步分析。""",
)
def extract_links_tool(
    url: str = Field(..., description="要提取链接的网页URL"),
    link_type: str = Field(
        default="all",
        description="链接类型：all（所有）, internal（内部）, external（外部）",
    ),
    timeout: int = Field(default=30, description="请求超时时间（秒）"),
):
    """
    从网页提取链接

    Args:
        url: 网页URL
        link_type: 链接类型筛选
        timeout: 超时时间

    Returns:
        str: 提取的链接列表
    """
    logger.info(f"🔗 提取链接: {url} (类型: {link_type})")

    try:
        from urllib.parse import urljoin, urlparse

        import requests
        from bs4 import BeautifulSoup

        # 发送请求
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        # 解析HTML
        soup = BeautifulSoup(response.content, "html.parser")
        links = soup.find_all("a", href=True)

        base_domain = urlparse(url).netloc
        result_links = []

        for link in links:
            href = link["href"]  # type: ignore
            full_url = urljoin(url, href)  # type: ignore
            link_domain = urlparse(full_url).netloc
            link_text = link.get_text().strip()

            # 根据类型筛选
            if link_type == "internal" and link_domain != base_domain:
                continue
            elif link_type == "external" and link_domain == base_domain:
                continue

            result_links.append(f"• {link_text}: {full_url}")

        if result_links:
            result = f"从 {url} 提取的链接 ({len(result_links)} 个):\n\n" + "\n".join(
                result_links[:50]
            )
            if len(result_links) > 50:
                result += f"\n\n... 还有 {len(result_links) - 50} 个链接未显示"
            logger.info(f"✅ 链接提取完成: {len(result_links)} 个")
        else:
            result = f"在 {url} 中未找到链接"

        return result

    except Exception as e:
        error_msg = f"提取链接失败: {str(e)}"
        logger.error(error_msg)
        return f"错误: {error_msg}"


# 🛠️
@tool(
    "enhanced_search_and_crawler_tool",
    description="此工具使用提供的关键字执行搜索，并获取以markdown格式显示的信息。",
)
def enhanced_search_and_crawler_tool(
    query: str = Field(description="要搜索的关键字。"),
) -> List:
    try:
        logger.info(f">>>>>>> [search_tool] input -> query: {query}")
        response = enhanced_web_search_tool.run(query)

        if response and isinstance(response, list):
            for item in response:
                if "url" in item:
                    _url = item["url"]
                    crawled_content = enhanced_web_crawler_tool.run(_url)
                    item["content"] = crawled_content
            logger.info(f"<<<<<<< [search_tool] output -> : {response}")
            return response

        return response
    except BaseException as e:
        error_msg = f"Failed to Serp. Error: {repr(e)}"
        logger.error(error_msg)
        return [error_msg]
