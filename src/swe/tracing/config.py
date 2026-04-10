# -*- coding: utf-8 -*-
"""Tracing configuration module.

Defines configuration classes for the tracing feature.
"""
from typing import Optional

from pydantic import BaseModel, Field

from ..database import DatabaseConfig


class TracingConfig(BaseModel):
    """Tracing feature configuration.

    This configuration controls the behavior of the tracing system
    which captures LLM calls, tool executions, and skill invocations.
    Database storage is required for tracing.
    """

    enabled: bool = Field(
        default=False,
        description="Enable tracing feature",
    )
    batch_size: int = Field(
        default=100,
        description="Batch size for bulk write to database",
    )
    flush_interval: int = Field(
        default=5,
        description="Flush interval in seconds for background writer",
    )
    retention_days: int = Field(
        default=30,
        description="Data retention period in days (0 = no cleanup)",
    )
    sanitize_output: bool = Field(
        default=True,
        description="Sanitize sensitive data in tool input/output",
    )
    max_output_length: int = Field(
        default=500,
        description="Maximum length for tool output strings",
    )
    database: Optional[DatabaseConfig] = Field(
        default=None,
        description="Database configuration for persistent storage (required)",
    )
