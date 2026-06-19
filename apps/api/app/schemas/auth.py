"""Auth + invite request/response DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import InviteKind, InviteStatus, Track


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    id: UUID
    type: str  # user | va
    email: str
    name: str
    role: str | None = None  # hunter | admin | super_admin | va
    platform_id: UUID | None = None
    platform_name: str | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=4, max_length=16)


class HunterInviteRequest(BaseModel):
    email: EmailStr


class AdminInviteRequest(BaseModel):
    email: EmailStr
    platform_id: UUID


class VaInviteRequest(BaseModel):
    email: EmailStr
    va_name: str = Field(min_length=1, max_length=200)
    whatsapp: str = Field(min_length=5, max_length=40)
    track: Track | None = None  # None = all-tracks assignment


class InviteOut(BaseModel):
    id: UUID
    email: str
    kind: InviteKind
    status: InviteStatus
    track: Track | None = None
    va_name: str | None = None
    platform_id: UUID | None = None
    expires_at: datetime
    created_at: datetime


class InviteCreatedResponse(InviteOut):
    """Returned once at creation — carries the raw key + a ready-to-share link."""

    key: str
    signup_link: str
