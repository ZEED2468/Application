"""Platform + admin-account DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
