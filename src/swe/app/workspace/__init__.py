# -*- coding: utf-8 -*-
"""Workspace module for agent lifecycle management.

This module provides unified workspace management including:
- Workspace: Single agent instance manager
- ServiceManager: Component lifecycle orchestration
- ServiceDescriptor: Declarative service configuration
"""

__all__ = ["Workspace", "ServiceManager", "ServiceDescriptor"]


def __getattr__(name: str):
    if name == "Workspace":
        from .workspace import Workspace as _Workspace

        return _Workspace
    if name in {"ServiceManager", "ServiceDescriptor"}:
        from .service_manager import (
            ServiceDescriptor as _ServiceDescriptor,
            ServiceManager as _ServiceManager,
        )

        exports = {
            "ServiceManager": _ServiceManager,
            "ServiceDescriptor": _ServiceDescriptor,
        }
        return exports[name]
    raise AttributeError(name)
