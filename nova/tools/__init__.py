# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from langchain_community.tools.file_management import (
    CopyFileTool,
    DeleteFileTool,
    FileSearchTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    WriteFileTool,
)

from .baidu_serper import SerpBaiduTool
from .file_manager import (
    CreateDirectoryTool,
    ReadJsonTool,
    WriteJsonTool,
)
from .format_result import MarkdownToHtmlTool
from .llm_searcher import LLMSearchTool
from .memory_manager import UpsertMemoryTool
from .web_crawler import CrawlTool
from .wechat_crawler import CrawlWechatTool
from .wechat_searcher import WechatSearchTool
from .wechat_serper import SerpWechatTool

# Create an instance
# 文件操作类工具
read_file_tool = ReadFileTool()
write_file_tool = WriteFileTool()
delete_file_tool = DeleteFileTool()
list_directory_tool = ListDirectoryTool()
copy_file_tool = CopyFileTool()
move_file_tool = MoveFileTool()
search_file_tool = FileSearchTool()

# 自定义工具实例化（可选指定 root_dir 限制操作范围）
create_directory_tool = CreateDirectoryTool()
write_json_tool = WriteJsonTool()
read_json_tool = ReadJsonTool()

# 百度搜索工具
serp_baidu_tool = SerpBaiduTool()

# 形式化结果工具
markdown_to_html_tool = MarkdownToHtmlTool()

# 网页爬取工具
web_crawler_tool = CrawlTool()

# 爬取微信公众号工具
crawl_wechat_tool = CrawlWechatTool()

# 微信公众号搜索工具
serp_wechat_tool = SerpWechatTool()

# 微信知识检索工具
wechat_searcher_tool = WechatSearchTool()

# 带有总结的网络搜索工具
llm_searcher_tool = LLMSearchTool()

# 更新记忆工具
upsert_memory_tool = UpsertMemoryTool()
