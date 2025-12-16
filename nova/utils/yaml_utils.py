# -*- coding: utf-8 -*-
# @Time   : 2025/05/12
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

import os
from typing import Any, Dict

import yaml


def replace_env_vars(value: str) -> str:
    """Replace environment variables in string values."""
    if not isinstance(value, str):
        return value
    if value.startswith("$"):
        env_var = value[1:]
        return os.getenv(env_var, value)
    return value


def process_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively process dictionary to replace environment variables."""
    result = {}
    for key, value in config.items():
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    value[i] = process_dict(item)
                elif isinstance(item, str):
                    value[i] = replace_env_vars(item)
            result[key] = value

        if isinstance(value, dict):
            result[key] = process_dict(value)
        elif isinstance(value, str):
            result[key] = replace_env_vars(value)
        else:
            result[key] = value
    return result


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """Load and process YAML configuration file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Config file '{file_path}' not found.")

    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    processed_config = process_dict(config)

    return processed_config
