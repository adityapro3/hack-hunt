from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)
    admin_signup_key: str | None = None


class SignInRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
