"""Pydantic schemas for sales."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.customers.schemas import CustomerModel
from src.products.schemas import ProductModel


class SaleModel(BaseModel):
    uid: uuid.UUID
    product_uid: uuid.UUID | None = None
    customer_uid: uuid.UUID | None = None
    user_uid: uuid.UUID | None = None
    quantity: int
    total_amount: float
    sold_at: datetime
    created_at: datetime


class SaleDetailModel(SaleModel):
    """A sale with its related product and customer expanded."""

    product: ProductModel | None = None
    customer: CustomerModel | None = None


class SaleCreateModel(BaseModel):
    product_uid: uuid.UUID
    customer_uid: uuid.UUID
    quantity: int = Field(default=1, gt=0)
    # Optional: computed as product.unit_price * quantity when omitted.
    total_amount: float | None = Field(default=None, gt=0)
    sold_at: datetime | None = None
