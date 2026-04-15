# -*- coding: utf-8 -*-
"""Cases configuration models.

Pydantic models for case definitions and user-case mappings.
Cases are stored in WORKING_DIR/cases.json (global definitions)
and WORKING_DIR/user_cases.json (user-case mappings).
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CaseStep(BaseModel):
    """A single step in case detail."""

    title: str = Field(..., description="Step title")
    content: str = Field(..., description="Step content/description")


class CaseDetail(BaseModel):
    """Case detail with iframe URL and steps."""

    iframe_url: str = Field(
        ...,
        description="URL to embed in iframe (required)",
    )
    iframe_title: str = Field(
        default="",
        description="Title displayed above iframe",
    )
    steps: List[CaseStep] = Field(
        default_factory=list,
        description="List of steps to display on left panel",
    )


class Case(BaseModel):
    """A single case definition."""

    id: str = Field(..., description="Unique case identifier")
    label: str = Field(..., description="Display label for case card")
    value: str = Field(..., description="Query text when user selects case")
    image_url: Optional[str] = Field(
        default=None,
        description="Optional image URL for case card",
    )
    sort_order: int = Field(
        default=0,
        description="Sort order for case list display",
    )
    is_active: bool = Field(
        default=True,
        description="Whether case is active and visible",
    )
    detail: Optional[CaseDetail] = Field(
        default=None,
        description="Case detail with iframe and steps",
    )


class CasesConfig(BaseModel):
    """Cases configuration stored in cases.json."""

    cases: List[Case] = Field(
        default_factory=list,
        description="List of all case definitions",
    )


class UserCasesConfig(BaseModel):
    """User-case mapping configuration stored in user_cases.json."""

    user_cases: dict[str, List[str]] = Field(
        default_factory=lambda: {"default": []},
        description="Mapping of userId to list of case IDs",
    )
