# -*- coding: utf-8 -*-
"""CoPaw Tracing Module - Link tracing and analytics.

This module provides tracing and analytics capabilities for CoPaw,
including event collection, storage, and aggregation.
"""

from .config import TracingConfig, TDSQLConfig
from .models import EventType, Span, Trace, TraceStatus
from .manager import (
    TraceManager,
    TraceContext,
    get_trace_manager,
    init_trace_manager,
    close_trace_manager,
    get_current_trace,
    set_current_trace,
    has_trace_manager,
)
from .store import TraceStore
from .database import TDSQLConnection
from .model_wrapper import TracingModelWrapper

__all__ = [
    # Config
    "TracingConfig",
    "TDSQLConfig",
    # Models
    "EventType",
    "Span",
    "Trace",
    "TraceStatus",
    # Manager
    "TraceManager",
    "TraceContext",
    "get_trace_manager",
    "init_trace_manager",
    "close_trace_manager",
    "get_current_trace",
    "set_current_trace",
    "has_trace_manager",
    # Store
    "TraceStore",
    # Database
    "TDSQLConnection",
    # Model wrapper
    "TracingModelWrapper",
]
