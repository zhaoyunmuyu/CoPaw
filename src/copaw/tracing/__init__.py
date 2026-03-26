# -*- coding: utf-8 -*-
"""CoPaw Tracing Module - Link tracing and analytics.

This module provides tracing and analytics capabilities for CoPaw,
including event collection, storage, and aggregation.
"""

from .config import TracingConfig, TDSQLConfig
from .models import EventType, Span, Trace, TraceStatus
from .manager import TraceManager, get_trace_manager, init_trace_manager, close_trace_manager
from .store import TraceStore
from .database import TDSQLConnection

__all__ = [
    "TracingConfig",
    "TDSQLConfig",
    "EventType",
    "Span",
    "Trace",
    "TraceStatus",
    "TraceManager",
    "TraceStore",
    "TDSQLConnection",
    "get_trace_manager",
    "init_trace_manager",
    "close_trace_manager",
]
