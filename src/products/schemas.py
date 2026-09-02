"""Pydantic schemas for products."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProductModel(BaseModel):
    uid: uuid.UUID
    name: str
    category: str | None = None
    unit_price: float
    created_at: datetime
    updated_at: datetime


class ProductCreateModel(BaseModel):
    name: str = Field(max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit_price: float = Field(gt=0)


class ProductUpdateModel(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit_price: float | None = Field(default=None, gt=0)
