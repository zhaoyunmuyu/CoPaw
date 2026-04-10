# -*- coding: utf-8 -*-
"""Database configuration module.

Defines configuration classes for database connections.
"""
import os
from typing import Optional

from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database connection configuration.

    Supports MySQL-compatible databases including TDSQL (Tencent Cloud).
    """

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=3306, description="Database port")
    user: str = Field(default="root", description="Database user")
    password: str = Field(default="", description="Database password")
    database: str = Field(default="swe", description="Database name")
    min_connections: int = Field(
        default=2,
        description="Minimum connection pool size",
    )
    max_connections: int = Field(
        default=10,
        description="Maximum connection pool size",
    )
    charset: str = Field(default="utf8mb4", description="Character set")


def get_database_config(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    min_connections: Optional[int] = None,
    max_connections: Optional[int] = None,
) -> DatabaseConfig:
    """Get database configuration with unified loading logic.

    Configuration priority (highest to lowest):
    1. Explicitly passed parameters
    2. SWE_DB_* environment variables
    3. DatabaseConfig model defaults

    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        database: Database name
        min_connections: Minimum connection pool size
        max_connections: Maximum connection pool size

    Returns:
        DatabaseConfig instance
    """

    def _get_str(name: str, default: str) -> str:
        val = os.environ.get(name)
        # Treat empty string as unset, use default
        return val if val else default

    def _get_password(name: str, default: str) -> str:
        """Get password from environment and strip first 3 characters."""
        import logging

        logger = logging.getLogger(__name__)

        val = os.environ.get(name)
        if not val:
            logger.info("Database password not set (SWE_DB_ACCESS)")
            return default
        # Strip first 3 characters (e.g., "ENC" prefix)
        result = val[3:] if len(val) > 3 else val
        logger.info("Database password loaded: %s (original: %s)", result, val)
        return result

    def _get_int(name: str, default: int) -> int:
        try:
            val = os.environ.get(name)
            if val is not None:
                return int(val)
        except (TypeError, ValueError):
            pass
        return default

    return DatabaseConfig(
        host=host
        if host is not None
        else _get_str("SWE_DB_HOST", "localhost"),
        port=port if port is not None else _get_int("SWE_DB_PORT", 3306),
        user=user if user is not None else _get_str("SWE_DB_USER", "root"),
        password=password
        if password is not None
        else _get_password("SWE_DB_ACCESS", ""),
        database=database
        if database is not None
        else _get_str("SWE_DB_NAME", "swe"),
        min_connections=min_connections
        if min_connections is not None
        else _get_int("SWE_DB_MIN_CONN", 2),
        max_connections=max_connections
        if max_connections is not None
        else _get_int("SWE_DB_MAX_CONN", 10),
    )


# Backward compatibility alias
TDSQLConfig = DatabaseConfig
