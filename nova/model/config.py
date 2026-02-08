# -*- coding: utf-8 -*-
# @Time   : 2026/02/06
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from nova.utils.log_utils import set_log

logger = logging.getLogger(__name__)


# ------------------------------ 基础配置模型 ------------------------------
class SystemConfig(BaseModel):
    """系统级配置模型"""

    IP_PORT: str = Field(..., description="服务监听的IP和端口")
    WORKERS: int = Field(..., ge=1, le=32, description="服务工作进程数（1-32）")
    TIMEOUT: int = Field(..., ge=60, description="服务超时时间（秒，最小60）")
    NAME: str = Field(..., description="服务名称")
    DESC: str = Field(..., description="服务描述")
    VERSION: str = Field(..., description="服务版本号")
    DEBUG: bool = Field(default=False, description="调试模式开关")

    store_dir: str = Field("./store", description="存储目录")
    cache_dir: str = Field("./cache", description="缓存目录")
    log_dir: str = Field("./logs", description="日志目录")
    task_dir: str = Field(..., description="任务目录（支持环境变量）")
    prompt_template_dir: str = Field(..., description="提示词模板目录（支持环境变量）")

    @field_validator("IP_PORT")
    @classmethod
    def validate_ip_port(cls, v: str) -> str:
        """校验IP:PORT格式"""
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError(f"IP_PORT格式错误: {v}，必须是 'ip:port' 格式")
        ip, port = parts
        # 简单校验端口范围
        try:
            port_int = int(port)
            if not (0 <= port_int <= 65535):
                raise ValueError(f"端口号 {port} 超出范围（0-65535）")
        except ValueError:
            raise ValueError(f"端口号 {port} 不是有效数字")
        return v

    @field_validator("task_dir", "prompt_template_dir")
    @classmethod
    def resolve_env_vars(cls, v: str) -> str:
        """解析环境变量（如 $TASK_DIR -> 实际路径）"""
        if not v:
            return v
        # 替换环境变量（支持 $VAR 或 ${VAR} 格式）
        resolved_path = os.path.expandvars(v)
        # 确保目录存在（可选）
        os.makedirs(resolved_path, exist_ok=True)
        return resolved_path


class LiteLLMParams(BaseModel):
    """LLM模型的litellm参数模型"""

    model: str = Field(..., description="模型名称（如 openai/Qwen3-235B-A22B）")
    api_base: str = Field(..., description="API基础地址（支持环境变量）")
    api_key: str = Field(..., description="API密钥（支持环境变量）")
    cache: bool = Field(default=False, description="是否启用缓存")
    verbose: bool = Field(default=True, description="是否输出详细日志")
    request_timeout: int = Field(default=600, ge=30, description="请求超时时间（秒）")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0, description="温度系数")
    top_p: float = Field(default=0.2, ge=0.0, le=1.0, description="Top P值")
    top_k: Optional[int] = Field(None, ge=1, description="Top K值")
    max_retries: int = Field(default=2, ge=0, le=10, description="最大重试次数")
    chat_template_kwargs: Optional[Dict[str, Any]] = Field(
        None, description="聊天模板参数"
    )

    @field_validator("api_base", "api_key")
    @classmethod
    def resolve_llm_env_vars(cls, v: str) -> str:
        """解析LLM配置中的环境变量"""
        return os.path.expandvars(v) if v else v


class LiteLLMModelConfig(BaseModel):
    """单个LLM模型配置"""

    model_name: str = Field(..., description="自定义模型名称（如 basic/reasoning）")
    litellm_params: LiteLLMParams = Field(..., description="litellm相关参数")


class LLMConfig(BaseModel):
    """LLM模型配置"""

    default_model_name: str = Field(..., description="默认使用的LLM模型名称")
    model_list: List[LiteLLMModelConfig] = Field(..., description="LLM模型列表")

    @model_validator(mode="after")
    def validate_default_model(self) -> LLMConfig:
        """校验默认模型是否在模型列表中"""
        model_names = [m.model_name for m in self.model_list]
        if self.default_model_name not in model_names:
            raise ValueError(
                f"默认LLM模型 {self.default_model_name} 不在模型列表中，可用模型: {model_names}"
            )
        return self


class EmbeddingModelConfig(BaseModel):
    """单个嵌入模型配置"""

    model_name: str = Field(..., description="嵌入模型名称")
    type: str = Field(
        ..., pattern=r"^openai$", description="嵌入模型类型（目前仅支持openai）"
    )
    name: str = Field(..., description="模型具体名称")
    base_url: str = Field(..., description="嵌入模型API基础地址")
    api_key: str = Field(default="", description="嵌入模型API密钥")
    timeout: int = Field(default=30, ge=10, description="请求超时时间（秒）")

    @field_validator("base_url")
    def validate_api_url(cls, v: str) -> str:
        """校验API地址格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"API地址格式错误: {v}，必须以http://或https://开头")
        return v


class EmbeddingConfig(BaseModel):
    """嵌入模型总配置"""

    default_model_name: str = Field(..., description="默认使用的嵌入模型名称")
    model_list: List[EmbeddingModelConfig] = Field(..., description="嵌入模型列表")

    @model_validator(mode="after")
    def validate_default_model(self) -> EmbeddingConfig:
        """校验默认模型是否在模型列表中"""
        model_names = [m.model_name for m in self.model_list]
        if self.default_model_name not in model_names:
            raise ValueError(
                f"默认嵌入模型 {self.default_model_name} 不在模型列表中，可用模型: {model_names}"
            )
        return self


class AgentNodeHooksConfig(BaseModel):
    """AgentHooks配置模型"""

    truncate_max_length: int = Field(
        default=1024, description="截断最大长度（超过此长度的文本将被截断）"
    )

    enable_timing: bool = Field(default=True, description="是否启用计时功能")


class HookConfig(BaseModel):
    """Hook配置模型"""

    Agent_Node_Hooks: AgentNodeHooksConfig = Field(
        default_factory=AgentNodeHooksConfig, description="AgentHooks配置"
    )


# ------------------------------ 总配置模型 ------------------------------
class AppConfig(BaseModel):
    """应用总配置模型（对应整个YAML文件）"""

    SYSTEM: SystemConfig = Field(..., description="系统配置")
    LLM: LLMConfig = Field(..., description="LLM模型配置")
    EMBEDDING: EmbeddingConfig = Field(..., description="嵌入模型配置")
    HOOK: HookConfig = Field(..., description="Hook配置")

    @classmethod
    def replace_env_vars(cls, value: str) -> str:
        """Replace environment variables in string values."""
        if not isinstance(value, str):
            return value
        if value.startswith("$"):
            env_var = value[1:]
            return os.getenv(env_var, value)
        return value

    @classmethod
    def process_dict(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively process dictionary to replace environment variables."""
        result = {}
        for key, value in config.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        value[i] = cls.process_dict(item)
                    elif isinstance(item, str):
                        value[i] = cls.replace_env_vars(item)
                result[key] = value

            if isinstance(value, dict):
                result[key] = cls.process_dict(value)
            elif isinstance(value, str):
                result[key] = cls.replace_env_vars(value)
            else:
                result[key] = value
        return result

    @classmethod
    def from_yaml(cls, yaml_path: str) -> AppConfig:
        """从YAML文件加载并解析配置"""
        try:
            import yaml
        except ImportError:
            raise ImportError("请安装pyyaml: pip install pyyaml")

        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Config file '{yaml_path}' not found.")

        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        processed_config = cls.process_dict(yaml_data)
        # 解析并校验配置
        return cls(**processed_config)

    @classmethod
    def set_dotenv(cls, env_path_override: Optional[str] = None) -> bool:
        """
        加载 .env 环境变量文件，支持自定义路径覆盖

        优先级：
        1. 函数入参 env_path_override（最高优先级）
        2. 系统环境变量 ENV_PATH
        3. 默认路径（当前文件向上三级目录的 .env 文件）

        Args:
            env_path_override: 自定义 .env 文件路径，优先级高于 ENV_PATH 和默认路径

        Returns:
            bool: 加载成功返回 True，失败返回 False

        Raises:
            无（所有异常捕获并记录日志，保证函数鲁棒性）
        """
        # 1. 确定最终的 .env 文件路径
        try:
            # 默认路径：当前文件向上三级目录的 .env
            default_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            # 优先级：自定义入参 > 系统环境变量 > 默认路径
            final_env_path = (
                env_path_override or os.environ.get("ENV_PATH") or str(default_env_path)
            )
            # 转换为 Path 对象，提升路径处理兼容性
            final_env_path = Path(final_env_path).resolve()

            # 2. 检查文件是否存在
            if not final_env_path.exists():
                logger.warning(f".env 文件不存在：{final_env_path}，跳过环境变量加载")
                return False

            # 3. 检查文件是否为普通文件（避免目录/链接等）
            if not final_env_path.is_file():
                logger.error(f"指定的 .env 路径不是有效文件：{final_env_path}")
                return False

            # 4. 加载环境变量
            load_dotenv(
                dotenv_path=final_env_path, override=False
            )  # override=False 避免覆盖已有系统环境变量
            logger.info(f"成功从 {final_env_path} 加载环境变量")
            return True

        except Exception as e:
            # 捕获所有异常，避免函数崩溃
            logger.error(f"加载 .env 文件失败：{str(e)}", exc_info=True)
            return False

    @classmethod
    def set_log(cls):
        set_log(cls.SYSTEM.log_dir)
