# -*- coding: utf-8 -*-
"""Memory management module for SWE agents."""

__all__ = [
    "AgentMdManager",
    "BaseMemoryManager",
    "ReMeLightMemoryManager",
]


def __getattr__(name: str):
    if name == "AgentMdManager":
        from .agent_md_manager import AgentMdManager as _AgentMdManager

        return _AgentMdManager
    if name == "BaseMemoryManager":
        from .base_memory_manager import (
            BaseMemoryManager as _BaseMemoryManager,
        )

        return _BaseMemoryManager
    if name == "ReMeLightMemoryManager":
        from .reme_light_memory_manager import (
            ReMeLightMemoryManager as _ReMeLightMemoryManager,
        )

        return _ReMeLightMemoryManager
    raise AttributeError(name)
