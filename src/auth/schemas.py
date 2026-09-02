"""Pydantic schemas for authentication."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateModel(BaseModel):
    first_name: str = Field(max_length=25)
    last_name: str = Field(max_length=25)
    username: str = Field(max_length=25)
    email: str = Field(max_length=60)
    password: str = Field(min_length=6)


class UserModel(BaseModel):
    uid: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str
    is_verified: bool
    role: str
    created_at: datetime
    updated_at: datetime


class UserLoginModel(BaseModel):
    email: str = Field(max_length=60)
    password: str = Field(min_length=6)


class EmailsModel(BaseModel):
    addresses: list[str]


class PasswordResetRequestModel(BaseModel):
    email: str


class PasswordResetConfirmModel(BaseModel):
    new_password: str = Field(min_length=6)
    confirm_new_password: str = Field(min_length=6)
