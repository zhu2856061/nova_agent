# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF
from nova.sandbox.local.local_sandbox_provider import LocalSandboxProvider
from nova.sandbox.sandbox import SandboxProvider

_default_sandbox_provider: SandboxProvider | None = None


def get_sandbox_provider() -> SandboxProvider:
    """Get the sandbox provider singleton.

    Returns a cached singleton instance. Use `reset_sandbox_provider()` to clear
    the cache, or `shutdown_sandbox_provider()` to properly shutdown and clear.

    Returns:
        A sandbox provider instance.
    """
    use = CONF.Sandbox.use
    global _default_sandbox_provider
    if _default_sandbox_provider is None:
        if use == "local":
            _default_sandbox_provider = LocalSandboxProvider()
        else:
            _default_sandbox_provider = LocalSandboxProvider()

    return _default_sandbox_provider
