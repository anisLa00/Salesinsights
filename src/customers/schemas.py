"""Pydantic schemas for customers."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CustomerModel(BaseModel):
    uid: uuid.UUID
    name: str
    email: str | None = None
    region: str | None = None
    created_at: datetime


class CustomerCreateModel(BaseModel):
    name: str = Field(max_length=200)
    email: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=100)


class CustomerUpdateModel(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=100)
