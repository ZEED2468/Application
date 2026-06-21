"""Platform + admin-account + source-board DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import JobSourceName


class PlatformCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PlatformUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class PlatformOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class AdminOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str  # admin | super_admin
    is_active: bool
    platform_id: UUID | None = None
    platform_name: str | None = None


# Board scrapers (Greenhouse/Lever/Ashby) are the only board sources.
_BOARD_SOURCES = {JobSourceName.greenhouse, JobSourceName.lever, JobSourceName.ashby}


class SourceBoardCreate(BaseModel):
    source: JobSourceName
    token: str = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=200)


class SourceBoardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: JobSourceName
    token: str
    label: str | None = None
    is_active: bool
    created_at: datetime
