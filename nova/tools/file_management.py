# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import os
from typing import Any, Type

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
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CreateDirectoryInput(BaseModel):
    directory_path: str = Field(
        ...,
        description="The path of the directory to create. "
        "The path should be a relative path from the root of the file system.",
    )


# 🛠️
class CreateDirectoryTool(BaseFileToolMixin, BaseTool):
    """Tool that create a directory"""

    name: str = "create_directory"
    args_schema: Type[BaseModel] = CreateDirectoryInput
    description: str = (
        "Use this tool to create a directory. "
        "The directory will be created in the root of the file system."
    )

    def _run(self, directory_path: str) -> str:
        try:
            dir_path = self.get_relative_path(directory_path)
        except FileValidationError:
            return INVALID_PATH_TEMPLATE.format(
                arg_name="file_path", value=directory_path
            )
        try:
            dir_path.parent.mkdir(exist_ok=True, parents=False)
            os.makedirs(dir_path, exist_ok=True)
            logging.info(f"Directory create successfully to {dir_path}.")
            return str(dir_path.resolve())
        except Exception as e:
            return "Error: " + str(e)

    # TODO: Add aiofiles method


class WriteJsonInput(BaseModel):
    """Input for WriteFileTool."""

    file_path: str = Field(..., description="name of file")
    jsonl: dict = Field(..., description="json to write to file")


# 🛠️
class WriteJsonTool(BaseFileToolMixin, BaseTool):  # type: ignore[override, override]
    """Tool that writes a json to disk."""

    name: str = "write_json_file"
    args_schema: Type[BaseModel] = WriteJsonInput
    description: str = "Write json file to disk"

    def _run(self, file_path: str, jsonl: dict) -> str:
        try:
            write_path = self.get_relative_path(file_path)
        except FileValidationError:
            return INVALID_PATH_TEMPLATE.format(arg_name="file_path", value=file_path)
        try:
            write_path.parent.mkdir(exist_ok=True, parents=False)
            with open(write_path, "w", encoding="utf-8") as f:
                json.dump(jsonl, f, ensure_ascii=False)
            return f"Json File written successfully to {file_path}."
        except Exception as e:
            return "Error: " + str(e)

    # TODO: Add aiofiles method


class ReadJsonInput(BaseModel):
    """Input for ReadFileTool."""

    file_path: str = Field(..., description="name of file")


# 🛠️
class ReadJsonTool(BaseFileToolMixin, BaseTool):
    """Tool that read a file to json."""

    name: str = "read_json_file"
    args_schema: Type[BaseModel] = ReadJsonInput
    description: str = "read a file to json"

    def _run(self, file_path: str) -> Any:
        try:
            read_path = self.get_relative_path(file_path)
        except FileValidationError:
            return INVALID_PATH_TEMPLATE.format(arg_name="file_path", value=file_path)
        try:
            with open(read_path, "r", encoding="utf-8") as f:
                jsonl = json.load(f)
            return jsonl
        except Exception as e:
            return "Error: " + str(e)


read_file_tool = ReadFileTool()
write_file_tool = WriteFileTool()
delete_file_tool = DeleteFileTool()
list_directory_tool = ListDirectoryTool()
copy_file_tool = CopyFileTool()
move_file_tool = MoveFileTool()
search_file_tool = FileSearchTool()
create_directory_tool = CreateDirectoryTool()

write_json_tool = WriteJsonTool()
read_json_tool = ReadJsonTool()
