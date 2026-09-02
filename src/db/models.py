"""SQLModel table definitions for Sales Insight.

Domain: a `User` (analyst) signs in and records `Sale` rows, each linking a
`Product` to a `Customer`. The AI insights are computed by aggregating sales.
"""

import uuid
from datetime import datetime
from typing import List, Optional

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    username: str
    email: str
    first_name: str
    last_name: str
    password_hash: str = Field(exclude=True)
    is_verified: bool = Field(default=False)
    role: str = Field(
        sa_column=Column(pg.VARCHAR, nullable=False, server_default="user")
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    verification_email_sent_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.now)
    )

    sales: List["Sale"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Product(SQLModel, table=True):
    __tablename__ = "products"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    name: str
    category: Optional[str] = None
    unit_price: float = Field(sa_column=Column(pg.NUMERIC(12, 2), nullable=False))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    sales: List["Sale"] = Relationship(
        back_populates="product", sa_relationship_kwargs={"lazy": "selectin"}
    )

    def __repr__(self) -> str:
        return f"<Product {self.name}>"


class Customer(SQLModel, table=True):
    __tablename__ = "customers"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    name: str
    email: Optional[str] = None
    region: Optional[str] = None
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    sales: List["Sale"] = Relationship(
        back_populates="customer", sa_relationship_kwargs={"lazy": "selectin"}
    )

    def __repr__(self) -> str:
        return f"<Customer {self.name}>"


class Sale(SQLModel, table=True):
    __tablename__ = "sales"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    quantity: int = Field(default=1)
    total_amount: float = Field(sa_column=Column(pg.NUMERIC(12, 2), nullable=False))
    product_uid: Optional[uuid.UUID] = Field(
        default=None, foreign_key="products.uid"
    )
    customer_uid: Optional[uuid.UUID] = Field(
        default=None, foreign_key="customers.uid"
    )
    user_uid: Optional[uuid.UUID] = Field(default=None, foreign_key="users.uid")
    sold_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    product: Optional[Product] = Relationship(
        back_populates="sales", sa_relationship_kwargs={"lazy": "selectin"}
    )
    customer: Optional[Customer] = Relationship(
        back_populates="sales", sa_relationship_kwargs={"lazy": "selectin"}
    )
    user: Optional[User] = Relationship(
        back_populates="sales", sa_relationship_kwargs={"lazy": "selectin"}
    )

    def __repr__(self) -> str:
        return f"<Sale {self.uid} qty={self.quantity} total={self.total_amount}>"
