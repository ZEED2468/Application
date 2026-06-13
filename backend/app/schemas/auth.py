"""Auth request/response DTOs."""

from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    id: UUID
    type: str  # user | va
    email: str
    name: str
    role: str | None = None
