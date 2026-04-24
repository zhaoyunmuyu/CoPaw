# -*- coding: utf-8 -*-
"""Featured case store (simplified - merged tables)."""

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
            SELECT case_id, label, value, image_url,
                   iframe_url, iframe_title, steps, sort_order
            FROM swe_featured_case
            WHERE source_id = %s AND bbk_id <=> %s AND is_active = 1
            ORDER BY sort_order ASC
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
        """Get case by case_id (global unique lookup).

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
        source_id: str,
        bbk_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FeaturedCase], int]:
        """List cases for a specific source_id with optional bbk_id filter.

        Args:
            source_id: Source identifier (required)
            bbk_id: BBK identifier (optional filter)
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (cases list, total count)
        """
        if not self._use_db:
            return [], 0

        where_clauses = ["source_id = %s"]
        params: list = [source_id]

        if bbk_id is not None:
            where_clauses.append("bbk_id <=> %s")
            params.append(bbk_id)

        where_sql = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) as total FROM swe_featured_case WHERE {where_sql}"
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        query = f"""
            SELECT * FROM swe_featured_case
            WHERE {where_sql}
            ORDER BY sort_order ASC, created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self.db.fetch_all(query, tuple(params))
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
                    (source_id, bbk_id, case_id, label, value, image_url,
                     iframe_url, iframe_title, steps, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            await self.db.execute(
                query,
                (
                    case.source_id,
                    case.bbk_id,
                    case.case_id,
                    case.label,
                    case.value,
                    case.image_url,
                    case.iframe_url,
                    case.iframe_title,
                    steps_json,
                    case.sort_order,
                    int(case.is_active),
                ),
            )
        return case

    async def update_case(
        self,
        case_id: str,
        bbk_id: Optional[str] = None,
        label: Optional[str] = None,
        value: Optional[str] = None,
        image_url: Optional[str] = None,
        iframe_url: Optional[str] = None,
        iframe_title: Optional[str] = None,
        steps: Optional[list[CaseStep]] = None,
        sort_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[FeaturedCase]:
        """Update case.

        Args:
            case_id: Case identifier
            bbk_id: New bbk_id
            label: New label
            value: New value
            image_url: New image URL
            iframe_url: New iframe URL
            iframe_title: New iframe title
            steps: New steps
            sort_order: New sort order
            is_active: New active status

        Returns:
            Updated FeaturedCase or None if not found
        """
        if not self._use_db:
            return None

        updates = []
        params: list = []

        if bbk_id is not None:
            updates.append("bbk_id = %s")
            params.append(bbk_id)
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
        if sort_order is not None:
            updates.append("sort_order = %s")
            params.append(sort_order)
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
        """Delete case.

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

    async def check_case_exists(
        self,
        source_id: str,
        case_id: str,
        bbk_id: Optional[str] = None,
    ) -> bool:
        """Check if case exists for given dimension.

        Args:
            source_id: Source identifier
            case_id: Case identifier
            bbk_id: BBK identifier (optional)

        Returns:
            True if exists, False otherwise
        """
        if not self._use_db:
            return False

        query = """
            SELECT COUNT(*) as cnt FROM swe_featured_case
            WHERE source_id = %s AND bbk_id <=> %s AND case_id = %s
        """
        row = await self.db.fetch_one(query, (source_id, bbk_id, case_id))
        return row["cnt"] > 0 if row else False

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
            source_id=row["source_id"],
            bbk_id=row["bbk_id"],
            case_id=row["case_id"],
            label=row["label"],
            value=row["value"],
            image_url=row["image_url"],
            iframe_url=row["iframe_url"],
            iframe_title=row["iframe_title"],
            steps=steps,
            sort_order=row["sort_order"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
