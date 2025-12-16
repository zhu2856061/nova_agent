# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Type, Union

from langchain_community.tools.file_management import (
    CopyFileTool,
    DeleteFileTool,
    FileSearchTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    WriteFileTool,
)
from langchain_community.tools.file_management.utils import (
    INVALID_PATH_TEMPLATE,
    BaseFileToolMixin,
    FileValidationError,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# 🛠️========================== 创建目录工具 ==========================
class CreateDirectoryInput(BaseModel):
    """输入模型：创建目录工具的参数校验"""

    directory_path: str = Field(
        ...,
        description=(
            "要创建的目录路径，必须是相对于文件系统根目录的相对路径；"
            "路径格式需符合当前操作系统规范（如 Linux/macOS 用 /，Windows 用 \\）"
        ),
    )

    @field_validator("directory_path")
    def validate_directory_path(cls, v: str) -> str:
        """校验目录路径合法性，避免空路径/非法字符"""
        if not v.strip():
            raise ValueError("目录路径不能为空")
        # 过滤非法字符（根据操作系统适配）
        illegal_chars = r'<>:"|?*' if os.name == "nt" else "/"
        if any(char in v for char in illegal_chars):
            raise ValueError(f"目录路径包含非法字符：{illegal_chars}")
        return v.strip()


class CreateDirectoryTool(BaseFileToolMixin, BaseTool):
    """
    自定义工具：创建目录
    继承 BaseFileToolMixin 以复用路径校验、相对路径转换等能力
    """

    name: str = "create_directory"
    args_schema: Type[BaseModel] = CreateDirectoryInput
    description: str = (
        "用于在文件系统中创建目录的工具；"
        "输入为相对路径，目录会创建在文件系统根目录下；"
        "支持创建单层目录，若父目录不存在会抛出异常（如需递归创建可调整 parents=True）"
    )
    # 可选：添加安全限制，指定允许创建目录的根路径
    root_dir: Optional[Path] = Field(default=None)

    def __init__(self, root_dir: Optional[Union[str, Path]] = None, **kwargs):
        """初始化工具，支持指定根目录（增强路径安全）"""
        super().__init__(**kwargs)
        if root_dir:
            self.root_dir = Path(root_dir).resolve()
            # 确保根目录存在
            self.root_dir.mkdir(exist_ok=True, parents=True)

    def _run(self, directory_path: str) -> str:
        """
        核心执行逻辑：创建目录
        Args:
            directory_path: 要创建的目录相对路径
        Returns:
            str: 成功返回目录绝对路径，失败返回错误信息
        """

        try:
            # 获取校验后的相对路径（BaseFileToolMixin 提供的方法）
            dir_path = self.get_relative_path(directory_path)
            # 若指定了根目录，拼接根目录路径（增强安全，限制创建范围）
            if self.root_dir:
                dir_path = self.root_dir / dir_path

            # 创建目录：parents=False 表示仅创建最后一级目录，父目录不存在则报错
            # 如需递归创建父目录，改为 parents=True
            dir_path.mkdir(exist_ok=True, parents=False)

            abs_path = dir_path.resolve()
            logger.info(f"目录创建成功：{abs_path}")
            return f"目录创建成功，绝对路径：{abs_path}"

        except FileValidationError as e:
            # 路径校验失败
            error_msg = INVALID_PATH_TEMPLATE.format(
                arg_name="directory_path", value=directory_path
            )
            logger.error(f"目录路径校验失败：{error_msg} | 详情：{str(e)}")
            return f"错误：{error_msg}"

        except PermissionError as e:
            # 权限不足
            error_msg = f"创建目录失败：权限不足，无法写入 {directory_path}"
            logger.error(f"{error_msg} | 详情：{str(e)}")
            return f"错误：{error_msg}"

        except Exception as e:
            # 其他异常
            error_msg = f"创建目录失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"

    async def _arun(self, directory_path: str) -> str:
        """
        异步版本：创建目录（基于 aiofiles 实现，需先安装 aiofiles）
        补充原代码 TODO 项
        """
        try:
            import aiofiles.os as aio_os

            dir_path = self.get_relative_path(directory_path)
            if self.root_dir:
                dir_path = self.root_dir / dir_path

            # 异步创建目录
            await aio_os.makedirs(dir_path, exist_ok=True)
            abs_path = dir_path.resolve()
            logger.info(f"异步创建目录成功：{abs_path}")
            return f"目录创建成功，绝对路径：{abs_path}"

        except Exception as e:
            error_msg = f"异步创建目录失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"


# 🛠️====================== 写入JSON文件工具 ==========================
class WriteJsonInput(BaseModel):
    """输入模型：写入JSON文件工具的参数校验"""

    file_path: str = Field(..., description="要写入的文件名称/路径（相对路径）")
    jsonl: dict = Field(..., description="要写入文件的JSON数据（字典格式）")

    @field_validator("file_path")
    def validate_file_path(cls, v: str) -> str:
        """校验文件路径合法性"""
        if not v.strip():
            raise ValueError("文件路径不能为空")
        # 确保文件后缀为 .json（可选，根据业务需求调整）
        if not v.endswith(".json"):
            logger.warning(
                f"文件路径 {v} 未以 .json 结尾，可能导致解析异常", UserWarning
            )
        return v.strip()

    @field_validator("jsonl")
    def validate_json_data(cls, v: dict) -> dict:
        """校验JSON数据合法性"""
        if not isinstance(v, dict):
            raise TypeError(f"JSON数据必须是字典类型，当前类型：{type(v)}")
        return v


class WriteJsonTool(BaseFileToolMixin, BaseTool):  # type: ignore[override, override]
    """
    自定义工具：写入JSON文件到磁盘
    继承 BaseFileToolMixin 以复用路径校验能力
    """

    name: str = "write_json_file"
    args_schema: Type[BaseModel] = WriteJsonInput
    description: str = (
        "用于将JSON格式数据写入文件的工具；"
        "输入为文件相对路径和字典类型的JSON数据；"
        "自动创建父目录（若不存在），文件编码为UTF-8"
    )
    root_dir: Optional[Path] = Field(default=None)

    def __init__(self, root_dir: Optional[Union[str, Path]] = None, **kwargs):
        super().__init__(**kwargs)
        if root_dir:
            self.root_dir = Path(root_dir).resolve()
            self.root_dir.mkdir(exist_ok=True, parents=True)

    def _run(self, file_path: str, jsonl: dict) -> str:
        """
        核心执行逻辑：写入JSON文件
        Args:
            file_path: 文件相对路径
            jsonl: 要写入的JSON字典数据
        Returns:
            str: 成功返回提示信息，失败返回错误信息
        """
        try:
            write_path = self.get_relative_path(file_path)
            if self.root_dir:
                write_path = self.root_dir / write_path

            # 确保父目录存在（parents=True 递归创建）
            write_path.parent.mkdir(exist_ok=True, parents=True)

            # 写入JSON文件：ensure_ascii=False 支持中文，indent=4 格式化输出
            with open(write_path, "w", encoding="utf-8") as f:
                json.dump(jsonl, f, ensure_ascii=False, indent=4)

            logger.info(f"JSON文件写入成功：{write_path.resolve()}")
            return f"JSON文件写入成功，路径：{write_path.resolve()}"

        except FileValidationError as e:
            error_msg = INVALID_PATH_TEMPLATE.format(
                arg_name="file_path", value=file_path
            )
            logger.error(f"文件路径校验失败：{error_msg} | 详情：{str(e)}")
            return f"错误：{error_msg}"

        except PermissionError as e:
            error_msg = f"写入JSON文件失败：权限不足，无法写入 {file_path}"
            logger.error(f"{error_msg} | 详情：{str(e)}")
            return f"错误：{error_msg}"

        except Exception as e:
            error_msg = f"写入JSON文件失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"

    async def _arun(self, file_path: str, jsonl: dict) -> str:
        """
        异步版本：写入JSON文件（补充原代码 TODO 项）
        """
        try:
            import aiofiles

            write_path = self.get_relative_path(file_path)
            if self.root_dir:
                write_path = self.root_dir / write_path

            write_path.parent.mkdir(exist_ok=True, parents=True)

            async with aiofiles.open(write_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(jsonl, ensure_ascii=False, indent=4))

            logger.info(f"异步写入JSON文件成功：{write_path.resolve()}")
            return f"JSON文件写入成功，路径：{write_path.resolve()}"

        except Exception as e:
            error_msg = f"异步写入JSON文件失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"


# 🛠️====================== 读取JSON文件工具 ==========================
class ReadJsonInput(BaseModel):
    """输入模型：读取JSON文件工具的参数校验"""

    file_path: str = Field(..., description="要读取的文件名称/路径（相对路径）")

    @field_validator("file_path")
    def validate_file_path(cls, v: str) -> str:
        """校验文件路径合法性"""
        if not v.strip():
            raise ValueError("文件路径不能为空")
        if not os.path.exists(v.strip()):
            raise FileNotFoundError(f"指定文件不存在：{v}")
        return v.strip()


class ReadJsonTool(BaseFileToolMixin, BaseTool):
    """
    自定义工具：从磁盘读取JSON文件并解析为字典
    """

    name: str = "read_json_file"
    args_schema: Type[BaseModel] = ReadJsonInput
    description: str = (
        "用于读取JSON文件并解析为字典的工具；"
        "输入为文件相对路径，输出为解析后的字典数据；"
        "仅支持合法的JSON格式文件，非JSON文件会抛出解析异常"
    )
    root_dir: Optional[Path] = Field(default=None)

    def __init__(self, root_dir: Optional[Union[str, Path]] = None, **kwargs):
        super().__init__(**kwargs)
        if root_dir:
            self.root_dir = Path(root_dir).resolve()

    def _run(self, file_path: str) -> Union[dict, str]:
        """
        核心执行逻辑：读取并解析JSON文件
        Returns:
            dict: 解析成功返回字典数据
            str: 失败返回错误信息
        """
        try:
            read_path = self.get_relative_path(file_path)
            if self.root_dir:
                read_path = self.root_dir / read_path

            # 读取并解析JSON文件
            with open(read_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            logger.info(f"JSON文件读取成功：{read_path.resolve()}")
            return json_data

        except FileValidationError as e:
            error_msg = INVALID_PATH_TEMPLATE.format(
                arg_name="file_path", value=file_path
            )
            logger.error(f"文件路径校验失败：{error_msg} | 详情：{str(e)}")
            return f"错误：{error_msg}"

        except json.JSONDecodeError as e:
            error_msg = (
                f"JSON文件解析失败：{file_path} 不是合法的JSON格式 | 详情：{str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"

        except Exception as e:
            error_msg = f"读取JSON文件失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"

    async def _arun(self, file_path: str) -> Union[dict, str]:
        """
        异步版本：读取JSON文件（补充原代码 TODO 项）
        """
        try:
            import aiofiles

            read_path = self.get_relative_path(file_path)
            if self.root_dir:
                read_path = self.root_dir / read_path

            async with aiofiles.open(read_path, "r", encoding="utf-8") as f:
                content = await f.read()
                json_data = json.loads(content)

            logger.info(f"异步读取JSON文件成功：{read_path.resolve()}")
            return json_data

        except Exception as e:
            error_msg = f"异步读取JSON文件失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"错误：{error_msg}"


# ========================== 工具实例化 ==========================
# 注意：可通过 root_dir 参数限制文件操作范围，增强安全性

read_file_tool = ReadFileTool()
write_file_tool = WriteFileTool()
delete_file_tool = DeleteFileTool()
list_directory_tool = ListDirectoryTool()
copy_file_tool = CopyFileTool()
move_file_tool = MoveFileTool()
search_file_tool = FileSearchTool()

# 示例：root_dir="./data" 表示所有文件操作都限制在 ./data 目录下
# 自定义工具实例化（可选指定 root_dir 限制操作范围）
create_directory_tool = CreateDirectoryTool(root_dir=None)
write_json_tool = WriteJsonTool(root_dir=None)
read_json_tool = ReadJsonTool(root_dir=None)


# ========================== 工具导出（便于外部调用） ==========================
__all__ = [
    # 原生工具实例
    "read_file_tool",
    "write_file_tool",
    "delete_file_tool",
    "list_directory_tool",
    "copy_file_tool",
    "move_file_tool",
    "search_file_tool",
    # 自定义工具类 & 实例
    "CreateDirectoryTool",
    "WriteJsonTool",
    "ReadJsonTool",
    "create_directory_tool",
    "write_json_tool",
    "read_json_tool",
    # 输入模型（便于外部校验参数）
    "CreateDirectoryInput",
    "WriteJsonInput",
    "ReadJsonInput",
]
