"""SQLModel table definitions for Sales Insight.

Domain: a `User` is a person/account. A `Business` is a tenant (e.g. "Anis
Electronics"); users join it through `BusinessMember`, which carries their
role. Products, customers and sales all belong to exactly one business —
that `business_uid` is the tenant boundary every query must be scoped by.

A `Sale` records both the owning business and the employee (`user_uid`) who
entered it.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, Relationship, SQLModel


class BusinessRole(str, Enum):
    """Roles a user can hold within a business, most privileged first."""

    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


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
    memberships: List["BusinessMember"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )
    businesses_owned: List["Business"] = Relationship(
        back_populates="owner", sa_relationship_kwargs={"lazy": "selectin"}
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Business(SQLModel, table=True):
    """A tenant. All products, customers and sales hang off a business."""

    __tablename__ = "businesses"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    name: str
    owner_uid: uuid.UUID = Field(foreign_key="users.uid", index=True)
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    owner: Optional[User] = Relationship(back_populates="businesses_owned")
    members: List["BusinessMember"] = Relationship(
        back_populates="business", sa_relationship_kwargs={"lazy": "selectin"}
    )
    products: List["Product"] = Relationship(back_populates="business")
    customers: List["Customer"] = Relationship(back_populates="business")
    sales: List["Sale"] = Relationship(back_populates="business")

    def __repr__(self) -> str:
        return f"<Business {self.name}>"


class BusinessMember(SQLModel, table=True):
    """Links a user to a business with a role.

    Membership is modelled separately (rather than a `business_uid` on User)
    so one person can belong to several businesses with different roles.
    """

    __tablename__ = "business_members"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    business_uid: uuid.UUID = Field(foreign_key="businesses.uid", index=True)
    user_uid: uuid.UUID = Field(foreign_key="users.uid", index=True)
    role: str = Field(default=BusinessRole.EMPLOYEE.value)
    is_active: bool = Field(default=True)
    joined_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    business: Optional[Business] = Relationship(back_populates="members")
    user: Optional[User] = Relationship(back_populates="memberships")

    def __repr__(self) -> str:
        return f"<BusinessMember {self.user_uid} @ {self.business_uid} ({self.role})>"


class BusinessInvitation(SQLModel, table=True):
    """A pending invitation for someone to join a business."""

    __tablename__ = "business_invitations"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    business_uid: uuid.UUID = Field(foreign_key="businesses.uid", index=True)
    email: str = Field(index=True)
    role: str = Field(default=BusinessRole.EMPLOYEE.value)
    status: str = Field(default=InvitationStatus.PENDING.value, index=True)
    invited_by_uid: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.uid"
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    expires_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, nullable=False))
    accepted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(pg.TIMESTAMP, nullable=True)
    )

    business: Optional[Business] = Relationship()

    def __repr__(self) -> str:
        return f"<BusinessInvitation {self.email} -> {self.business_uid}>"


class Product(SQLModel, table=True):
    __tablename__ = "products"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, nullable=False, primary_key=True, default=uuid.uuid4)
    )
    name: str
    category: Optional[str] = None
    unit_price: float = Field(sa_column=Column(pg.NUMERIC(12, 2), nullable=False))
    business_uid: uuid.UUID = Field(foreign_key="businesses.uid", index=True)
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    business: Optional[Business] = Relationship(back_populates="products")
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
    business_uid: uuid.UUID = Field(foreign_key="businesses.uid", index=True)
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    business: Optional[Business] = Relationship(back_populates="customers")
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
    # The employee who recorded the sale.
    user_uid: Optional[uuid.UUID] = Field(default=None, foreign_key="users.uid")
    business_uid: uuid.UUID = Field(foreign_key="businesses.uid", index=True)
    sold_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))

    business: Optional[Business] = Relationship(back_populates="sales")
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
