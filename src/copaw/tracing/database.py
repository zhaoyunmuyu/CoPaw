# -*- coding: utf-8 -*-
"""TDSQL database connection module.

Provides async connection pool management for TDSQL (MySQL-compatible).
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from pydantic import BaseModel

from .config import TDSQLConfig

logger = logging.getLogger(__name__)

# Try to import aiomysql, fall back to None if not available
try:
    import aiomysql
    AIOMYSQL_AVAILABLE = True
except ImportError:
    AIOMYSQL_AVAILABLE = False
    logger.warning("aiomysql not installed, tracing will use in-memory storage")


class TDSQLConnection:
    """TDSQL database connection with async connection pool.

    Uses aiomysql for async MySQL operations.
    """

    def __init__(self, config: TDSQLConfig):
        """Initialize database connection.

        Args:
            config: TDSQL configuration
        """
        self.config = config
        self._pool: Optional[Any] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected and self._pool is not None

    async def connect(self) -> None:
        """Create connection pool."""
        if not AIOMYSQL_AVAILABLE:
            logger.warning("aiomysql not available, skipping database connection")
            self._connected = False
            return

        if self._pool is not None:
            return

        try:
            self._pool = await aiomysql.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                db=self.config.database,
                charset=self.config.charset,
                minsize=self.config.min_connections,
                maxsize=self.config.max_connections,
                autocommit=True,
            )
            self._connected = True
            logger.info(
                "TDSQL connection pool created: %s:%s/%s",
                self.config.host,
                self.config.port,
                self.config.database,
            )
        except Exception as e:
            logger.error("Failed to create TDSQL connection pool: %s", e)
            self._connected = False
            raise

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False
            logger.info("TDSQL connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool.

        Yields:
            aiomysql.Connection: Database connection
        """
        if self._pool is None:
            raise RuntimeError("Database not connected")
        async with self._pool.acquire() as conn:
            yield conn

    async def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> int:
        """Execute a query and return affected rows.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Number of affected rows
        """
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount

    async def execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> int:
        """Execute a query multiple times with different parameters.

        Args:
            query: SQL query
            params_list: List of parameter tuples

        Returns:
            Number of affected rows
        """
        if not params_list:
            return 0
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(query, params_list)
                return cur.rowcount

    async def fetch_one(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> Optional[dict]:
        """Fetch a single row.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row as dict or None
        """
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def fetch_all(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> list[dict]:
        """Fetch all rows.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [dict(row) for row in rows] if rows else []


# SQL Schema definitions

TRACES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    session_id VARCHAR(256) NOT NULL,
    channel VARCHAR(64) NOT NULL,
    start_time DATETIME(3) NOT NULL,
    end_time DATETIME(3),
    duration_ms INT,
    model_name VARCHAR(128),
    total_input_tokens INT DEFAULT 0,
    total_output_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    tools_used JSON,
    skills_used JSON,
    status VARCHAR(32) DEFAULT 'running',
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_start_time (start_time),
    INDEX idx_model_name (model_name),
    INDEX idx_session_id (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SPANS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS spans (
    span_id VARCHAR(36) PRIMARY KEY,
    trace_id VARCHAR(36) NOT NULL,
    parent_span_id VARCHAR(36),
    name VARCHAR(256) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    start_time DATETIME(3) NOT NULL,
    end_time DATETIME(3),
    duration_ms INT,
    user_id VARCHAR(128),
    session_id VARCHAR(256),
    channel VARCHAR(64),
    model_name VARCHAR(128),
    input_tokens INT,
    output_tokens INT,
    tool_name VARCHAR(128),
    skill_name VARCHAR(128),
    tool_input JSON,
    tool_output TEXT,
    error TEXT,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_trace_id (trace_id),
    INDEX idx_event_type (event_type),
    INDEX idx_tool_name (tool_name),
    INDEX idx_skill_name (skill_name),
    INDEX idx_user_id (user_id),
    INDEX idx_start_time (start_time),
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

USER_DAILY_STATS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_daily_stats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    stat_date DATE NOT NULL,
    total_tokens INT DEFAULT 0,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    session_count INT DEFAULT 0,
    conversation_count INT DEFAULT 0,
    total_duration_ms BIGINT DEFAULT 0,
    models_used JSON,
    tools_used JSON,
    skills_used JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_date (user_id, stat_date),
    INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

GLOBAL_DAILY_STATS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS global_daily_stats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_users INT DEFAULT 0,
    active_users INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    session_count INT DEFAULT 0,
    conversation_count INT DEFAULT 0,
    avg_duration_ms INT DEFAULT 0,
    model_distribution JSON,
    tool_distribution JSON,
    skill_distribution JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


async def init_database(conn: TDSQLConnection) -> None:
    """Initialize database tables.

    Args:
        conn: Database connection
    """
    if not conn.is_connected:
        logger.warning("Database not connected, skipping table initialization")
        return

    async with conn.acquire() as db_conn:
        async with db_conn.cursor() as cur:
            await cur.execute(TRACES_TABLE_SQL)
            await cur.execute(SPANS_TABLE_SQL)
            await cur.execute(USER_DAILY_STATS_TABLE_SQL)
            await cur.execute(GLOBAL_DAILY_STATS_TABLE_SQL)
    logger.info("Database tables initialized")
