import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.tools import BaseTool, StructuredTool

# 定义默认工具描述（语义更清晰，适配大模型理解）
LIST_FILES_TOOL_DESCRIPTION = (
    "列出指定路径下的所有文件和目录，支持绝对路径/相对路径，自动处理路径标准化。"
    "参数：path - 目标路径（字符串，不能为空）；"
    "返回：路径下的文件/目录路径列表（字符串格式），路径不存在/无权限时返回友好提示，结果过长时自动截断。"
)

# 截断配置（可灵活调整）
TRUNCATE_THRESHOLD = 100  # 列表元素超过此数量时截断
TRUNCATE_REMINDER = f"\n[提示] 结果过长，仅展示前{TRUNCATE_THRESHOLD}条内容"


def _ls_tool_generator(
    custom_description: str | None = None,
) -> BaseTool:
    """
    生成增强版 ls 工具（列出文件/目录），包含同步/异步实现，完善的错误处理和结果截断。

    Args:
        custom_description: 自定义工具描述（可选）

    Returns:
        配置好的 StructuredTool 实例
    """
    tool_description = custom_description or LIST_FILES_TOOL_DESCRIPTION

    # -------------------------- 1. 路径验证（内部工具函数） --------------------------
    def _validate_path(path: str) -> Path:
        """验证并标准化路径，处理空值、相对路径、用户目录（~），抛出友好异常"""
        if not isinstance(path, str) or not path.strip():
            raise ValueError("路径不能为空，请传入有效的文件/目录路径（字符串类型）")

        # 标准化路径：展开 ~、处理相对路径 → 转为绝对路径
        normalized_path = Path(path.strip()).expanduser().resolve()
        return normalized_path

    # -------------------------- 2. 同步获取文件信息（核心逻辑） --------------------------
    def ls_info(path: Path) -> List[Dict[str, Any]]:
        """
        同步获取指定路径下的文件/目录信息
        Args:
            path: 标准化后的 Path 对象
        Returns:
            包含文件/目录路径的字典列表（格式：[{"path": "完整路径"}, ...]）
        """
        file_infos = []
        try:
            # 遍历路径下的所有条目（文件+目录）
            for entry in os.scandir(path):
                file_infos.append({"path": entry.path})

        # 捕获常见异常，返回友好提示（而非直接崩溃）
        except FileNotFoundError:
            raise FileNotFoundError(f"路径不存在：{path}")
        except PermissionError:
            raise PermissionError(f"无权限访问路径：{path}")
        except Exception as e:
            raise RuntimeError(f"读取路径失败：{str(e)}")

        return file_infos

    # -------------------------- 3. 异步获取文件信息（核心逻辑） --------------------------
    async def als_info(path: Path) -> List[Dict[str, Any]]:
        """
        异步版本的文件信息获取（兼容异步调用场景）
        注：os.scandir 无原生异步，此处用 asyncio.to_thread 适配异步上下文
        """
        try:
            # 把同步操作放到线程池，避免阻塞事件循环
            file_infos = await asyncio.to_thread(ls_info, path)
            return file_infos
        except Exception as e:
            raise e

    # -------------------------- 4. 结果截断工具函数 --------------------------
    def truncate_if_too_long(items: List[str]) -> str:
        """如果结果列表过长，截断并添加提示"""
        if len(items) > TRUNCATE_THRESHOLD:
            truncated = items[:TRUNCATE_THRESHOLD]
            return f"{truncated}{TRUNCATE_REMINDER}"
        return str(items)

    # -------------------------- 5. 同步工具入口函数 --------------------------
    def sync_ls(path: str) -> str:
        """
        同步 ls 工具入口（对外暴露的工具函数）
        Args:
            path: 用户传入的路径字符串
        Returns:
            格式化的文件路径列表（字符串），含异常友好提示
        """
        try:
            validated_path = _validate_path(path)
            infos = ls_info(validated_path)
            # 提取路径列表并格式化
            paths = [fi.get("path", "") for fi in infos]
            result = truncate_if_too_long(paths)
            return result
        except Exception as e:
            # 捕获所有异常，返回友好提示（避免工具调用崩溃）
            return f"执行 ls 工具失败：{str(e)}"

    # -------------------------- 6. 异步工具入口函数 --------------------------
    async def async_ls(path: str) -> str:
        """
        异步 ls 工具入口（对外暴露的工具函数）
        """
        try:
            validated_path = _validate_path(path)
            infos = await als_info(validated_path)
            paths = [fi.get("path", "") for fi in infos]
            result = truncate_if_too_long(paths)
            return result
        except Exception as e:
            return f"执行异步 ls 工具失败：{str(e)}"

    # -------------------------- 7. 创建并返回结构化工具 --------------------------
    return StructuredTool.from_function(
        name="ls",
        description=tool_description,
        func=sync_ls,  # 同步函数入口
        coroutine=async_ls,  # 异步函数入口（可选，支持异步调用）
    )


# -------------------------- 沙箱配置（可根据需求调整） --------------------------
# 沙箱根目录（所有操作仅限此目录内）
SANDBOX_ROOT = Path("./sandbox_workspace").expanduser().resolve()
# 默认工具描述（强调沙箱限制）
LIST_FILES_TOOL_DESCRIPTION = (
    "在沙箱环境下列出指定路径下的所有文件和目录，仅允许访问沙箱根目录内的路径。"
    "参数：path - 沙箱内的目标路径（字符串，支持相对路径/绝对路径，不能为空）；"
    "返回：沙箱内的文件/目录路径列表（字符串格式），越权/不存在/无权限时返回友好提示，结果过长时自动截断。"
)
# 截断配置
TRUNCATE_THRESHOLD = 100
TRUNCATE_REMINDER = f"\n[沙箱提示] 结果过长，仅展示前{TRUNCATE_THRESHOLD}条内容"
# 操作日志存储（可替换为文件/数据库）
SANDBOX_OP_LOGS: List[Dict[str, Any]] = []


def _sandbox_ls_tool_generator(
    custom_description: str | None = None, custom_sandbox_root: Path | None = None
) -> BaseTool:
    """
    生成沙箱版 ls 工具（严格限制文件访问范围，隔离操作环境）

    Args:
        custom_description: 自定义工具描述（可选）
        custom_sandbox_root: 自定义沙箱根目录（可选，默认使用 SANDBOX_ROOT）

    Returns:
        配置好的 StructuredTool 实例
    """
    # 初始化沙箱根目录（优先使用自定义目录，否则用默认）
    sandbox_root = custom_sandbox_root or SANDBOX_ROOT
    # 确保沙箱根目录存在（自动创建）
    sandbox_root.mkdir(parents=True, exist_ok=True)

    tool_description = custom_description or LIST_FILES_TOOL_DESCRIPTION

    # -------------------------- 1. 沙箱路径安全验证（核心） --------------------------
    def _validate_sandbox_path(path: str) -> Path:
        """
        沙箱路径验证：
        1. 校验路径非空；
        2. 标准化路径；
        3. 检测是否在沙箱根目录内，禁止越权访问；
        4. 抛出安全异常（越权/非法路径）
        """
        # 基础空值校验
        if not isinstance(path, str) or not path.strip():
            raise ValueError(
                "[沙箱错误] 路径不能为空，请传入有效的沙箱内路径（字符串类型）"
            )

        # 标准化路径（展开~、处理相对路径）
        user_path = Path(path.strip()).expanduser()
        # 如果是相对路径 → 基于沙箱根目录拼接；如果是绝对路径 → 直接验证
        if not user_path.is_absolute():
            validated_path = (sandbox_root / user_path).resolve()
        else:
            validated_path = user_path.resolve()

        # 核心：检测是否越权（路径不在沙箱根目录内）
        try:
            # 判断 validated_path 是否是 sandbox_root 的子目录
            validated_path.relative_to(sandbox_root)
        except ValueError:
            raise PermissionError(
                f"[沙箱安全拦截] 禁止访问沙箱外路径！"
                f"\n沙箱根目录：{sandbox_root}"
                f"\n尝试访问的路径：{validated_path}"
            )

        return validated_path

    # -------------------------- 2. 操作日志记录 --------------------------
    def _log_sandbox_operation(
        path: str, operation: str = "ls", status: str = "success", message: str = ""
    ):
        """记录沙箱操作日志"""
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": operation,
            "target_path": path,
            "sandbox_root": str(sandbox_root),
            "status": status,  # success/failed
            "message": message,
        }
        SANDBOX_OP_LOGS.append(log_entry)
        # 可选：打印日志（生产环境可写入文件/数据库）
        print(f"[沙箱日志] {log_entry}")

    # -------------------------- 3. 同步获取沙箱内文件信息 --------------------------
    def ls_info(path: Path) -> List[Dict[str, Any]]:
        """同步获取沙箱内指定路径的文件/目录信息（只读）"""
        file_infos = []
        try:
            # 仅读取，不执行任何写操作
            for entry in os.scandir(path):
                # 只返回相对路径（隐藏沙箱根目录的绝对路径，增强安全性）
                relative_path = entry.path.replace(str(sandbox_root), "[沙箱根目录]")
                file_infos.append({"path": relative_path})

        except FileNotFoundError:
            raise FileNotFoundError(f"[沙箱错误] 沙箱内路径不存在：{path}")
        except PermissionError:
            raise PermissionError(f"[沙箱错误] 无权限访问沙箱内路径：{path}")
        except Exception as e:
            raise RuntimeError(f"[沙箱错误] 读取路径失败：{str(e)}")

        return file_infos

    # -------------------------- 4. 异步获取沙箱内文件信息 --------------------------
    async def als_info(path: Path) -> List[Dict[str, Any]]:
        """异步获取沙箱内文件信息（适配异步调用）"""
        try:
            file_infos = await asyncio.to_thread(ls_info, path)
            return file_infos
        except Exception as e:
            raise e

    # -------------------------- 5. 结果截断 --------------------------
    def truncate_if_too_long(items: List[str]) -> str:
        """截断过长的结果列表"""
        if len(items) > TRUNCATE_THRESHOLD:
            truncated = items[:TRUNCATE_THRESHOLD]
            return f"{truncated}{TRUNCATE_REMINDER}"
        return str(items)

    # -------------------------- 6. 同步沙箱 ls 工具入口 --------------------------
    def sync_sandbox_ls(path: str) -> str:
        """沙箱版同步 ls 工具入口（对外暴露）"""
        try:
            # 1. 沙箱路径验证（核心安全步骤）
            validated_path = _validate_sandbox_path(path)
            # 2. 获取文件信息
            infos = ls_info(validated_path)
            # 3. 提取路径列表并截断
            paths = [fi.get("path", "") for fi in infos]
            result = truncate_if_too_long(paths)
            # 4. 记录成功日志
            _log_sandbox_operation(
                path=path,
                operation="ls",
                status="success",
                message=f"成功列出 {validated_path} 下的 {len(paths)} 个条目",
            )
            return result

        except Exception as e:
            # 记录失败日志
            _log_sandbox_operation(
                path=path, operation="ls", status="failed", message=str(e)
            )
            return f"[沙箱 ls 工具执行失败] {str(e)}"

    # -------------------------- 7. 异步沙箱 ls 工具入口 --------------------------
    async def async_sandbox_ls(path: str) -> str:
        """沙箱版异步 ls 工具入口（对外暴露）"""
        try:
            validated_path = _validate_sandbox_path(path)
            infos = await als_info(validated_path)
            paths = [fi.get("path", "") for fi in infos]
            result = truncate_if_too_long(paths)
            _log_sandbox_operation(
                path=path,
                operation="async_ls",
                status="success",
                message=f"异步成功列出 {validated_path} 下的 {len(paths)} 个条目",
            )
            return result

        except Exception as e:
            _log_sandbox_operation(
                path=path, operation="async_ls", status="failed", message=str(e)
            )
            return f"[沙箱异步 ls 工具执行失败] {str(e)}"

    # -------------------------- 8. 创建沙箱版结构化工具 --------------------------
    return StructuredTool.from_function(
        name="sandbox_ls",  # 工具名明确标识沙箱版
        description=tool_description,
        func=sync_sandbox_ls,
        coroutine=async_sandbox_ls,
    )


# # -------------------------- 测试沙箱版 ls 工具 --------------------------
# if __name__ == "__main__":
#     # 1. 生成沙箱 ls 工具实例
#     sandbox_ls_tool = _sandbox_ls_tool_generator()

#     # 2. 测试1：列出沙箱内当前目录（合法）
#     print("=== 测试1：列出沙箱内当前目录 ===")
#     result1 = sandbox_ls_tool.invoke({"path": "."})
#     print(result1)

#     # 3. 测试2：尝试访问沙箱外路径（越权，被拦截）
#     print("\n=== 测试2：尝试访问沙箱外路径 ===")
#     result2 = sandbox_ls_tool.invoke({"path": "/root"})
#     print(result2)

#     # 4. 测试3：尝试通过 ../ 突破沙箱（被拦截）
#     print("\n=== 测试3：尝试通过 ../ 突破沙箱 ===")
#     result3 = sandbox_ls_tool.invoke({"path": "../../etc"})
#     print(result3)

#     # 5. 测试4：异步调用沙箱 ls
#     async def test_async_sandbox_ls():
#         print("\n=== 测试4：异步列出沙箱内当前目录 ===")
#         result4 = await sandbox_ls_tool.ainvoke({"path": "."})
#         print(result4)

#     asyncio.run(test_async_sandbox_ls())

#     # 6. 查看操作日志
#     print("\n=== 沙箱操作日志 ===")
#     for log in SANDBOX_OP_LOGS:
#         print(log)
