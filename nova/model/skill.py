# -*- coding: utf-8 -*-
# @Time   : 2026/02/06
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from pydantic import BaseModel


class SkillMetadata(BaseModel):
    """Metadata for a skill per Agent Skills specification (https://agentskills.io/specification)."""

    name: str
    """Skill identifier (max 64 chars, lowercase alphanumeric and hyphens)."""

    description: str
    """What the skill does (max 1024 chars)."""

    path: str
    """Path to the SKILL.md file."""

    license: str | None
    """License name or reference to bundled license file."""

    compatibility: str | None
    """Environment requirements (max 500 chars)."""

    metadata: dict[str, str]
    """Arbitrary key-value mapping for additional metadata."""

    allowed_tools: list[str]
    """Space-delimited list of pre-approved tools. (Experimental)"""
