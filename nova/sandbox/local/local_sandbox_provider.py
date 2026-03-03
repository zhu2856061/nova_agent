# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from pathlib import Path

from nova import CONF
from nova.sandbox.local.local_sandbox import LocalSandbox
from nova.sandbox.sandbox import Sandbox, SandboxProvider

_singleton: LocalSandbox | None = None


class LocalSandboxProvider(SandboxProvider):
    def __init__(self):
        """Initialize the local sandbox provider with path mappings."""
        self._path_mappings = self._setup_path_mappings()

    def _setup_path_mappings(self) -> dict[str, str]:
        """
        Setup path mappings for local sandbox.

        Maps container paths to actual local paths, including skills directory.

        Returns:
            Dictionary of path mappings
        """
        mappings = {}

        # Map skills container path to local skills directory
        try:
            skills_path = Path(CONF.SYSTEM.skill_dir)
            container_path = CONF.Sandbox.container_path

            # Only add mapping if skills directory exists
            if container_path:
                mappings[container_path] = str(skills_path)
        except Exception as e:
            # Log but don't fail if config loading fails
            print(f"Warning: Could not setup skills path mapping: {e}")

        return mappings

    def acquire(self, thread_id: str | None = None) -> str:
        global _singleton
        if _singleton is None:
            _singleton = LocalSandbox("local", path_mappings=self._path_mappings)
        return _singleton.id

    def get(self, sandbox_id: str) -> Sandbox | None:
        if sandbox_id == "local":
            if _singleton is None:
                self.acquire()
            return _singleton
        return None

    def release(self, sandbox_id: str) -> None:
        # LocalSandbox uses singleton pattern - no cleanup needed.
        # Note: This method is intentionally not called by SandboxMiddleware
        # to allow sandbox reuse across multiple turns in a thread.
        # For Docker-based providers (e.g., AioSandboxProvider), cleanup
        # happens at application shutdown via the shutdown() method.
        pass
