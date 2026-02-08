# -*- coding: utf-8 -*-
# @Time   : 2025/08/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Type

import markdown
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MarkdownToHtmlToolInput(BaseModel):
    md_content: str = Field(
        description="The Markdown content to convert to HTML.",
    )
    output_file: str = Field(
        description="The output file name for the HTML content.",
    )
    highlight_code: bool = Field(
        default=True,
        description="是否启用代码高亮",
    )


class MarkdownToHtmlTool(BaseTool):
    args_schema: Type[BaseModel] = MarkdownToHtmlToolInput
    description: str = "A tool that converts Markdown content to HTML."
    name: str = "markdown_to_html"

    def process_special_links(self, md_content):
        """
        处理特殊格式的链接：[数字] 来源名称: URL
        转换为标准Markdown链接格式
        """
        # 正则表达式匹配特殊链接格式
        pattern = r"\[(\d+)\]\s+([^:]+):\s+(\S+)"
        # 替换为标准Markdown链接格式，并保留引用标记
        processed = re.sub(pattern, r"\[\1\] [\2](\3)", md_content)
        return processed

    async def _arun(
        self, md_content: str, output_file: str, highlight_code: bool = True
    ):
        """
        将 Markdown 内容转换为 HTML 并保存到文件

        参数:
            md_content: Markdown 格式的文本内容
            output_file: 输出的 HTML 文件名
            highlight_code: 是否启用代码高亮
        """
        # 先处理特殊格式的链接
        md_content = self.process_special_links(md_content)
        # 配置扩展
        extensions = []
        if highlight_code:
            # 需要先安装 pygments: pip install pygments
            extensions.append("codehilite")

        # 添加常用扩展
        extensions.extend(
            [
                "extra",  # 包含表格、脚注等额外功能
                "tables",  # 支持表格
                "fenced_code",  # 支持围栏式代码块
                "toc",  # 生成目录
            ]
        )

        # 转换 Markdown 为 HTML
        html_content = markdown.markdown(
            md_content,
            extensions=extensions,
            extension_configs={
                "codehilite": {
                    "linenums": True,  # 显示行号
                    "css_class": "highlight",  # CSS 类名
                },
                "toc": {
                    "title": "目录"  # 目录标题
                },
            },
        )

        # 创建完整的 HTML 文档
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Markdown 转换结果</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
        }}
        th {{
            background-color: #f8f9fa;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding: 0 15px;
            color: #666;
        }}
        .toc {{
            background-color: #f8f9fa;
            padding: 1em;
            border-radius: 4px;
            margin-bottom: 2em;
        }}
        .toc-title {{
            font-weight: bold;
            margin-bottom: 0.5em;
        }}
        .highlight {{
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 1em;
            overflow-x: auto;
        }}
        pre {{
            margin: 0;
        }}
    </style>
    {'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/github.min.css">' if highlight_code else ""}
</head>
<body>
    {html_content}
</body>
</html>"""

        # 保存到文件
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_html)

        logger.info(f"转换完成，已保存到 {os.path.abspath(output_file)}")

    def _run(self, md_content: str, output_file: str, highlight_code: bool = True):
        """Synchronous wrapper for the async crawl function."""
        return asyncio.run(self._arun(md_content, output_file, highlight_code))
