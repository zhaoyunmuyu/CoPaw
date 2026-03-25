# -*- coding: utf-8 -*-
"""Aggregation queries for tracing analytics.

Provides aggregation functions for computing statistics from trace data.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from .database import TDSQLConnection
from .models import DailyStats, ModelUsage, ToolUsage, SkillUsage

logger = logging.getLogger(__name__)


async def aggregate_daily_stats(
    db: TDSQLConnection,
    date: Optional[datetime] = None,
) -> None:
    """Aggregate daily statistics for a given date.

    Computes and stores user and global daily statistics.

    Args:
        db: Database connection
        date: Date to aggregate (defaults to today)
    """
    if date is None:
        date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    start_time = date
    end_time = date + timedelta(days=1)

    # Aggregate user daily stats
    await _aggregate_user_daily_stats(db, start_time, end_time)

    # Aggregate global daily stats
    await _aggregate_global_daily_stats(db, start_time, end_time)


async def _aggregate_user_daily_stats(
    db: TDSQLConnection,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """Aggregate user daily statistics."""
    # Get user stats from traces
    query = """
        SELECT
            user_id,
            COUNT(*) as session_count,
            COUNT(DISTINCT session_id) as conversation_count,
            SUM(total_input_tokens) as input_tokens,
            SUM(total_output_tokens) as output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(duration_ms) as total_duration_ms,
            GROUP_CONCAT(DISTINCT model_name) as models,
            GROUP_CONCAT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(tools_used, '$'))) as tools,
            GROUP_CONCAT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(skills_used, '$'))) as skills
        FROM traces
        WHERE start_time >= %s AND start_time < %s
        GROUP BY user_id
    """
    rows = await db.fetch_all(query, (start_time, end_time))

    stat_date = start_time.date()

    for row in rows:
        # Upsert user daily stats
        upsert_query = """
            INSERT INTO user_daily_stats (
                user_id, stat_date, total_tokens, input_tokens, output_tokens,
                session_count, conversation_count, total_duration_ms,
                models_used, tools_used, skills_used
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_tokens = VALUES(total_tokens),
                input_tokens = VALUES(input_tokens),
                output_tokens = VALUES(output_tokens),
                session_count = VALUES(session_count),
                conversation_count = VALUES(conversation_count),
                total_duration_ms = VALUES(total_duration_ms),
                models_used = VALUES(models_used),
                tools_used = VALUES(tools_used),
                skills_used = VALUES(skills_used),
                updated_at = CURRENT_TIMESTAMP
        """
        await db.execute(upsert_query, (
            row["user_id"],
            stat_date,
            row["total_tokens"] or 0,
            row["input_tokens"] or 0,
            row["output_tokens"] or 0,
            row["session_count"] or 0,
            row["conversation_count"] or 0,
            row["total_duration_ms"] or 0,
            row["models"],
            row["tools"],
            row["skills"],
        ))


async def _aggregate_global_daily_stats(
    db: TDSQLConnection,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """Aggregate global daily statistics."""
    # Get global stats from traces
    query = """
        SELECT
            COUNT(DISTINCT user_id) as active_users,
            COUNT(*) as session_count,
            COUNT(DISTINCT session_id) as conversation_count,
            SUM(total_input_tokens) as input_tokens,
            SUM(total_output_tokens) as output_tokens,
            SUM(total_tokens) as total_tokens,
            AVG(duration_ms) as avg_duration_ms
        FROM traces
        WHERE start_time >= %s AND start_time < %s
    """
    row = await db.fetch_one(query, (start_time, end_time))

    if row is None:
        return

    # Get model distribution
    model_query = """
        SELECT model_name, COUNT(*) as count, SUM(total_tokens) as tokens
        FROM traces
        WHERE start_time >= %s AND start_time < %s AND model_name IS NOT NULL
        GROUP BY model_name
        ORDER BY count DESC
    """
    model_rows = await db.fetch_all(model_query, (start_time, end_time))
    model_distribution = {
        row["model_name"]: {"count": row["count"], "tokens": row["tokens"]}
        for row in model_rows
    }

    # Get tool distribution
    tool_query = """
        SELECT tool_name, COUNT(*) as count
        FROM spans
        WHERE start_time >= %s AND start_time < %s AND tool_name IS NOT NULL
        GROUP BY tool_name
        ORDER BY count DESC
    """
    tool_rows = await db.fetch_all(tool_query, (start_time, end_time))
    tool_distribution = {
        row["tool_name"]: row["count"]
        for row in tool_rows
    }

    # Get skill distribution
    skill_query = """
        SELECT skill_name, COUNT(*) as count
        FROM spans
        WHERE start_time >= %s AND start_time < %s AND skill_name IS NOT NULL
        GROUP BY skill_name
        ORDER BY count DESC
    """
    skill_rows = await db.fetch_all(skill_query, (start_time, end_time))
    skill_distribution = {
        row["skill_name"]: row["count"]
        for row in skill_rows
    }

    stat_date = start_time.date()

    # Upsert global daily stats
    upsert_query = """
        INSERT INTO global_daily_stats (
            stat_date, total_users, active_users, total_tokens,
            input_tokens, output_tokens, session_count, conversation_count,
            avg_duration_ms, model_distribution, tool_distribution, skill_distribution
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            active_users = VALUES(active_users),
            total_tokens = VALUES(total_tokens),
            input_tokens = VALUES(input_tokens),
            output_tokens = VALUES(output_tokens),
            session_count = VALUES(session_count),
            conversation_count = VALUES(conversation_count),
            avg_duration_ms = VALUES(avg_duration_ms),
            model_distribution = VALUES(model_distribution),
            tool_distribution = VALUES(tool_distribution),
            skill_distribution = VALUES(skill_distribution),
            updated_at = CURRENT_TIMESTAMP
    """
    await db.execute(upsert_query, (
        stat_date,
        row["active_users"] or 0,
        row["active_users"] or 0,
        row["total_tokens"] or 0,
        row["input_tokens"] or 0,
        row["output_tokens"] or 0,
        row["session_count"] or 0,
        row["conversation_count"] or 0,
        int(row["avg_duration_ms"] or 0),
        json.dumps(model_distribution),
        json.dumps(tool_distribution),
        json.dumps(skill_distribution),
    ))


async def get_daily_trend(
    db: TDSQLConnection,
    start_date: datetime,
    end_date: datetime,
) -> list[DailyStats]:
    """Get daily trend statistics.

    Args:
        db: Database connection
        start_date: Start date
        end_date: End date

    Returns:
        List of daily statistics
    """
    query = """
        SELECT
            stat_date,
            total_users,
            active_users,
            total_tokens,
            input_tokens,
            output_tokens,
            session_count,
            conversation_count,
            avg_duration_ms
        FROM global_daily_stats
        WHERE stat_date >= %s AND stat_date <= %s
        ORDER BY stat_date
    """
    rows = await db.fetch_all(query, (start_date.date(), end_date.date()))

    return [
        DailyStats(
            date=str(row["stat_date"]),
            total_users=row["total_users"] or 0,
            active_users=row["active_users"] or 0,
            total_tokens=row["total_tokens"] or 0,
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["output_tokens"] or 0,
            session_count=row["session_count"] or 0,
            conversation_count=row["conversation_count"] or 0,
            avg_duration_ms=row["avg_duration_ms"] or 0,
        )
        for row in rows
    ]


async def cleanup_old_data(
    db: TDSQLConnection,
    retention_days: int = 30,
) -> int:
    """Clean up old trace data.

    Args:
        db: Database connection
        retention_days: Number of days to retain

    Returns:
        Number of traces deleted
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    # Delete old traces (cascades to spans)
    query = "DELETE FROM traces WHERE start_time < %s"
    await db.execute(query, (cutoff_date,))

    # Delete old user daily stats
    stats_query = "DELETE FROM user_daily_stats WHERE stat_date < %s"
    await db.execute(stats_query, (cutoff_date.date(),))

    # Delete old global daily stats
    global_query = "DELETE FROM global_daily_stats WHERE stat_date < %s"
    await db.execute(global_query, (cutoff_date.date(),))

    logger.info("Cleaned up trace data older than %s", cutoff_date)
    return 0  # Could return actual count if needed
