"""Pydantic schemas for sales."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.customers.schemas import CustomerModel
from src.products.schemas import ProductModel


class SaleEmployeeModel(BaseModel):
    """The employee who recorded the sale."""

    uid: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str


class SaleModel(BaseModel):
    uid: uuid.UUID
    business_uid: uuid.UUID
    product_uid: uuid.UUID | None = None
    customer_uid: uuid.UUID | None = None
    user_uid: uuid.UUID | None = None
    quantity: int
    total_amount: float
    sold_at: datetime
    created_at: datetime


class SaleDetailModel(SaleModel):
    """A sale with its product, customer, and recording employee expanded."""

    product: ProductModel | None = None
    customer: CustomerModel | None = None
    user: SaleEmployeeModel | None = None


class SaleCreateModel(BaseModel):
    """Input for recording a sale.

    Deliberately minimal: the business comes from the validated business
    context, the employee from the JWT, and `total_amount` is computed
    server-side from the product's unit price. None of those are accepted
    from the client.
    """

    product_uid: uuid.UUID
    customer_uid: uuid.UUID
    quantity: int = Field(default=1, gt=0)
    sold_at: datetime | None = None
