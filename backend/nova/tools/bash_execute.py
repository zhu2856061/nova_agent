# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import logging
import subprocess

from langchain_core.tools import tool
from pydantic import Field

# Initialize logger
logger = logging.getLogger(__name__)


@tool("bash_execute_tool", description="使用此工具执行bash命令并执行必要的操作")
def bash_execute_tool(
    cmd: str = Field(..., description="要执行的bash命令"),
    timeout: int = Field(..., description="命令完成的最长时间（秒）"),
) -> str:
    try:
        # Execute the command and capture output
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        # Return stdout as the result
        return result.stdout
    except subprocess.CalledProcessError as e:
        # If command fails, return error information
        error_message = f"Command failed with exit code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}"
        logger.error(error_message)
        return error_message
    except subprocess.TimeoutExpired:
        # Handle timeout exception
        error_message = f"Command '{cmd}' timed out after {timeout}s."
        logger.error(error_message)
        return error_message
    except Exception as e:
        # Catch any other exceptions
        error_message = f"Error executing command: {str(e)}"
        logger.error(error_message)
        return error_message
