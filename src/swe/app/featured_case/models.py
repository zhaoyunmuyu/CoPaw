# -*- coding: utf-8 -*-
"""Featured case models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CaseStep(BaseModel):
    """Case step."""

    title: str
    content: str


class CaseDetail(BaseModel):
    """Case detail with iframe and steps."""

    iframe_url: str = ""
    iframe_title: str = ""
    steps: List[CaseStep] = []


class FeaturedCase(BaseModel):
    """Featured case definition."""

    model_config = ConfigDict(use_enum_values=True)

    id: Optional[int] = None
    case_id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., min_length=1)
    image_url: Optional[str] = Field(None, max_length=1024)
    iframe_url: Optional[str] = Field(None, max_length=1024)
    iframe_title: Optional[str] = Field(None, max_length=256)
    steps: Optional[List[CaseStep]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FeaturedCaseCreate(BaseModel):
    """Create featured case request."""

    case_id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., min_length=1)
    image_url: Optional[str] = Field(None, max_length=1024)
    iframe_url: Optional[str] = Field(None, max_length=1024)
    iframe_title: Optional[str] = Field(None, max_length=256)
    steps: Optional[List[CaseStep]] = None


class FeaturedCaseUpdate(BaseModel):
    """Update featured case request."""

    label: Optional[str] = Field(None, min_length=1, max_length=512)
    value: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=1024)
    iframe_url: Optional[str] = Field(None, max_length=1024)
    iframe_title: Optional[str] = Field(None, max_length=256)
    steps: Optional[List[CaseStep]] = None
    is_active: Optional[bool] = None


class CaseConfigItem(BaseModel):
    """Case config item for dimension mapping."""

    case_id: str = Field(..., min_length=1, max_length=64)
    sort_order: int = 0


class CaseConfigCreate(BaseModel):
    """Create case config request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    bbk_id: Optional[str] = Field(None, max_length=64)
    case_ids: List[CaseConfigItem] = []


class FeaturedCaseListResponse(BaseModel):
    """Featured case list response."""

    cases: List[FeaturedCase]
    total: int


class CaseConfigListItem(BaseModel):
    """Case config list item."""

    source_id: str
    bbk_id: Optional[str] = None
    case_count: int = 0


class CaseConfigListResponse(BaseModel):
    """Case config list response."""

    configs: List[CaseConfigListItem]
    total: int


class CaseConfigDetail(BaseModel):
    """Case config detail response."""

    source_id: str
    bbk_id: Optional[str] = None
    case_ids: List[str] = []
