# -*- coding: utf-8 -*-
"""Models for download task store."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DownloadTaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    filename: Optional[str] = None
    backend: str
    source: str
    status: DownloadTaskStatus = DownloadTaskStatus.PENDING
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
