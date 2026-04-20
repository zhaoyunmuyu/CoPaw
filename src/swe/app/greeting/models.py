# -*- coding: utf-8 -*-
"""Greeting configuration models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GreetingConfig(BaseModel):
    """Greeting configuration."""

    model_config = ConfigDict(use_enum_values=True)

    id: Optional[int] = None
    source_id: str = Field(..., min_length=1, max_length=64)
    bbk_id: Optional[str] = Field(None, max_length=64)
    greeting: str = Field(..., min_length=1, max_length=512)
    subtitle: Optional[str] = Field(None, max_length=512)
    placeholder: Optional[str] = Field(None, max_length=256)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GreetingConfigCreate(BaseModel):
    """Create greeting config request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    bbk_id: Optional[str] = Field(None, max_length=64)
    greeting: str = Field(..., min_length=1, max_length=512)
    subtitle: Optional[str] = Field(None, max_length=512)
    placeholder: Optional[str] = Field(None, max_length=256)


class GreetingConfigUpdate(BaseModel):
    """Update greeting config request."""

    greeting: Optional[str] = Field(None, min_length=1, max_length=512)
    subtitle: Optional[str] = Field(None, max_length=512)
    placeholder: Optional[str] = Field(None, max_length=256)
    is_active: Optional[bool] = None


class GreetingDisplay(BaseModel):
    """Greeting display response."""

    greeting: str
    subtitle: Optional[str] = None
    placeholder: Optional[str] = None


class GreetingConfigListResponse(BaseModel):
    """Greeting config list response."""

    configs: list[GreetingConfig]
    total: int
