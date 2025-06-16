# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging

from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from pydantic import Field

logger = logging.getLogger(__name__)


# 🛠️
@tool(
    "python_repl_tool",
    description="使用这个工具来执行python代码并进行数据分析或计算。如果要查看值的输出，应使用`print(...)`将其打印出来。这对用户可见",
)
def python_repl_tool(
    code: str = Field(..., description="要执行以进行进一步分析或计算的python代码"),
):
    if not isinstance(code, str):
        error_msg = f"Invalid input: code must be a string, got {type(code)}"
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    logger.info("Executing Python code")
    try:
        repl = PythonREPL()
        result = repl.run(code)
        # Check if the result is an error message by looking for typical error patterns
        if isinstance(result, str) and ("Error" in result or "Exception" in result):
            logger.error(result)
            return f"Error executing code:\n```python\n{code}\n```\nError: {result}"
        logger.info("Code execution successful")
    except BaseException as e:
        error_msg = repr(e)
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    return result_str
