# -*- coding: utf-8 -*-
"""Tracing configuration module.

Defines configuration classes for tracing and TDSQL database connection.
"""
from typing import Optional

from pydantic import BaseModel, Field


class TDSQLConfig(BaseModel):
    """TDSQL database connection configuration.

    TDSQL is Tencent Cloud's distributed database, MySQL-compatible.
    """

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=3306, description="Database port")
    user: str = Field(default="root", description="Database user")
    password: str = Field(default="", description="Database password")
    database: str = Field(default="copaw_tracing", description="Database name")
    min_connections: int = Field(default=2, description="Minimum connection pool size")
    max_connections: int = Field(default=10, description="Maximum connection pool size")
    charset: str = Field(default="utf8mb4", description="Character set")


class TracingConfig(BaseModel):
    """Tracing feature configuration."""

    enabled: bool = Field(default=False, description="Enable tracing feature")
    batch_size: int = Field(default=100, description="Batch size for bulk write")
    flush_interval: int = Field(default=5, description="Flush interval in seconds")
    retention_days: int = Field(default=30, description="Data retention period in days")
    sanitize_output: bool = Field(default=True, description="Sanitize sensitive data")
    max_output_length: int = Field(default=500, description="Max tool output length")
    database: Optional[TDSQLConfig] = Field(
        default=None,
        description="Database configuration",
    )
