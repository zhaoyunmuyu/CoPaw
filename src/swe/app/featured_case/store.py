# -*- coding: utf-8 -*-
"""Featured case store."""

import json
import logging
from typing import Any, Optional

from .models import CaseStep, FeaturedCase

logger = logging.getLogger(__name__)


class FeaturedCaseStore:
    """Store for featured case operations."""

    def __init__(self, db: Optional[Any] = None):
        """Initialize store.

        Args:
            db: Database connection (TDSQLConnection)
        """
        self.db = db
        self._use_db = db is not None and db.is_connected

    # ==================== Case display queries ====================

    async def get_cases_for_dimension(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> list[dict]:
        """Get cases for a specific dimension.

        Exact match: source_id=X AND bbk_id=Y
        Returns empty list if no match.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            List of case dicts for display
        """
        if not self._use_db:
            return []

        query = """
            SELECT c.case_id, c.label, c.value, c.image_url,
                   c.iframe_url, c.iframe_title, c.steps,
                   cc.sort_order
            FROM swe_featured_case_config cc
            JOIN swe_featured_case c ON cc.case_id = c.case_id
            WHERE cc.source_id = %s AND cc.bbk_id <=> %s
                AND cc.is_active = 1 AND c.is_active = 1
            ORDER BY cc.sort_order ASC
        """
        rows = await self.db.fetch_all(query, (source_id, bbk_id))

        result = []
        for row in rows:
            steps = None
            if row["steps"]:
                try:
                    steps = json.loads(row["steps"])
                except json.JSONDecodeError:
                    steps = None

            detail = None
            if row["iframe_url"] or steps:
                detail = {
                    "iframe_url": row["iframe_url"] or "",
                    "iframe_title": row["iframe_title"] or "",
                    "steps": steps or [],
                }

            result.append(
                {
                    "id": row["case_id"],
                    "label": row["label"],
                    "value": row["value"],
                    "image_url": row["image_url"],
                    "sort_order": row["sort_order"],
                    "detail": detail,
                },
            )
        return result

    async def get_case_by_id(self, case_id: str) -> Optional[FeaturedCase]:
        """Get case by case_id.

        Args:
            case_id: Case identifier

        Returns:
            FeaturedCase if found, None otherwise
        """
        if not self._use_db:
            return None

        query = "SELECT * FROM swe_featured_case WHERE case_id = %s"
        row = await self.db.fetch_one(query, (case_id,))
        return self._row_to_case(row) if row else None

    # ==================== Case CRUD ====================

    async def list_cases(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FeaturedCase], int]:
        """List all cases with pagination.

        Args:
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (cases list, total count)
        """
        if not self._use_db:
            return [], 0

        count_query = "SELECT COUNT(*) as total FROM swe_featured_case"
        count_row = await self.db.fetch_one(count_query)
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        query = """
            SELECT * FROM swe_featured_case
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        rows = await self.db.fetch_all(query, (page_size, offset))
        cases = [self._row_to_case(row) for row in rows]
        return cases, total

    async def create_case(self, case: FeaturedCase) -> FeaturedCase:
        """Create case.

        Args:
            case: FeaturedCase to create

        Returns:
            Created FeaturedCase
        """
        if self._use_db:
            steps_json = (
                json.dumps([s.model_dump() for s in case.steps])
                if case.steps
                else None
            )
            query = """
                INSERT INTO swe_featured_case
                    (case_id, label, value, image_url, iframe_url,
                     iframe_title, steps, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            await self.db.execute(
                query,
                (
                    case.case_id,
                    case.label,
                    case.value,
                    case.image_url,
                    case.iframe_url,
                    case.iframe_title,
                    steps_json,
                    int(case.is_active),
                ),
            )
        return case

    async def update_case(
        self,
        case_id: str,
        label: Optional[str] = None,
        value: Optional[str] = None,
        image_url: Optional[str] = None,
        iframe_url: Optional[str] = None,
        iframe_title: Optional[str] = None,
        steps: Optional[list[CaseStep]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[FeaturedCase]:
        """Update case.

        Args:
            case_id: Case identifier
            label: New label
            value: New value
            image_url: New image URL
            iframe_url: New iframe URL
            iframe_title: New iframe title
            steps: New steps
            is_active: New active status

        Returns:
            Updated FeaturedCase or None if not found
        """
        if not self._use_db:
            return None

        updates = []
        params: list = []

        if label is not None:
            updates.append("label = %s")
            params.append(label)
        if value is not None:
            updates.append("value = %s")
            params.append(value)
        if image_url is not None:
            updates.append("image_url = %s")
            params.append(image_url)
        if iframe_url is not None:
            updates.append("iframe_url = %s")
            params.append(iframe_url)
        if iframe_title is not None:
            updates.append("iframe_title = %s")
            params.append(iframe_title)
        if steps is not None:
            updates.append("steps = %s")
            params.append(
                json.dumps([s.model_dump() for s in steps]) if steps else None,
            )
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(int(is_active))

        if not updates:
            return None

        params.append(case_id)
        query = f"""
            UPDATE swe_featured_case
            SET {', '.join(updates)}
            WHERE case_id = %s
        """
        await self.db.execute(query, tuple(params))
        return await self.get_case_by_id(case_id)

    async def delete_case(self, case_id: str) -> bool:
        """Delete case (cascades to swe_featured_case_config).

        Args:
            case_id: Case identifier

        Returns:
            True if deleted, False otherwise
        """
        if self._use_db:
            query = "DELETE FROM swe_featured_case WHERE case_id = %s"
            result = await self.db.execute(query, (case_id,))
            return result > 0
        return False

    async def check_case_exists(self, case_id: str) -> bool:
        """Check if case exists.

        Args:
            case_id: Case identifier

        Returns:
            True if exists, False otherwise
        """
        if not self._use_db:
            return False

        query = (
            "SELECT COUNT(*) as cnt FROM swe_featured_case WHERE case_id = %s"
        )
        row = await self.db.fetch_one(query, (case_id,))
        return row["cnt"] > 0 if row else False

    # ==================== Case-Config operations ====================

    async def list_configs(
        self,
        source_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """List all configs with pagination.

        Args:
            source_id: Filter by source_id (optional)
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (configs list, total count)
        """
        if not self._use_db:
            return [], 0

        where_clauses = ["1=1"]
        params: list = []

        if source_id:
            where_clauses.append("source_id = %s")
            params.append(source_id)

        where_sql = " AND ".join(where_clauses)

        # Get unique source_id + bbk_id combinations
        count_query = f"""
            SELECT COUNT(DISTINCT CONCAT(
                source_id, COALESCE(bbk_id, '')
            )) as total
            FROM swe_featured_case_config
            WHERE {where_sql}
        """
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        query = f"""
            SELECT source_id, bbk_id, COUNT(*) as case_count
            FROM swe_featured_case_config
            WHERE {where_sql}
            GROUP BY source_id, bbk_id
            ORDER BY source_id, bbk_id
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self.db.fetch_all(query, tuple(params))

        configs = [
            {
                "source_id": row["source_id"],
                "bbk_id": row["bbk_id"],
                "case_count": row["case_count"],
            }
            for row in rows
        ]
        return configs, total

    async def get_config_cases(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> list[str]:
        """Get case_ids for a dimension config.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            List of case_ids in sort_order
        """
        if not self._use_db:
            return []

        query = """
            SELECT case_id FROM swe_featured_case_config
            WHERE source_id = %s AND bbk_id <=> %s AND is_active = 1
            ORDER BY sort_order
        """
        rows = await self.db.fetch_all(query, (source_id, bbk_id))
        return [row["case_id"] for row in rows]

    async def upsert_config(
        self,
        source_id: str,
        bbk_id: Optional[str],
        case_ids: list[dict],
    ) -> bool:
        """Upsert case config for dimension.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)
            case_ids: List of {case_id, sort_order}

        Returns:
            True if successful
        """
        if not self._use_db:
            return False

        # Delete existing config
        delete_query = """
            DELETE FROM swe_featured_case_config
            WHERE source_id = %s AND bbk_id <=> %s
        """
        await self.db.execute(delete_query, (source_id, bbk_id))

        # Insert new config
        if case_ids:
            insert_query = """
                INSERT INTO swe_featured_case_config
                    (source_id, bbk_id, case_id, sort_order, is_active)
                VALUES (%s, %s, %s, %s, 1)
            """
            params_list = [
                (source_id, bbk_id, item["case_id"], item["sort_order"])
                for item in case_ids
            ]
            await self.db.execute_many(insert_query, params_list)

        return True

    async def delete_config(
        self,
        source_id: str,
        bbk_id: Optional[str],
    ) -> bool:
        """Delete case config for dimension.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            True if deleted, False otherwise
        """
        if self._use_db:
            query = """
                DELETE FROM swe_featured_case_config
                WHERE source_id = %s AND bbk_id <=> %s
            """
            result = await self.db.execute(query, (source_id, bbk_id))
            return result > 0
        return False

    def _row_to_case(self, row: dict) -> FeaturedCase:
        """Convert row to FeaturedCase.

        Args:
            row: Database row dict

        Returns:
            FeaturedCase instance
        """
        steps = None
        if row.get("steps"):
            try:
                steps_data = json.loads(row["steps"])
                steps = [CaseStep(**s) for s in steps_data]
            except json.JSONDecodeError:
                steps = None

        return FeaturedCase(
            id=row["id"],
            case_id=row["case_id"],
            label=row["label"],
            value=row["value"],
            image_url=row["image_url"],
            iframe_url=row["iframe_url"],
            iframe_title=row["iframe_title"],
            steps=steps,
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
