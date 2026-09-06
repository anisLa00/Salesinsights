"""Database operations for customers.

Every query is scoped by ``business_uid`` so a customer id from another tenant
never resolves.
"""

import uuid

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Customer

from .schemas import CustomerCreateModel, CustomerUpdateModel


class CustomerService:
    async def get_all_customers(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> list[Customer]:
        statement = (
            select(Customer)
            .where(Customer.business_uid == business_uid)
            .order_by(desc(Customer.created_at))
        )
        result = await session.exec(statement)
        return result.all()

    async def get_customer(
        self, business_uid: uuid.UUID, customer_uid: uuid.UUID, session: AsyncSession
    ) -> Customer | None:
        statement = select(Customer).where(
            Customer.uid == customer_uid,
            Customer.business_uid == business_uid,
        )
        result = await session.exec(statement)
        return result.first()

    async def create_customer(
        self,
        business_uid: uuid.UUID,
        customer_data: CustomerCreateModel,
        session: AsyncSession,
    ) -> Customer:
        new_customer = Customer(
            **customer_data.model_dump(), business_uid=business_uid
        )
        session.add(new_customer)
        await session.commit()
        await session.refresh(new_customer)
        return new_customer

    async def update_customer(
        self,
        business_uid: uuid.UUID,
        customer_uid: uuid.UUID,
        update_data: CustomerUpdateModel,
        session: AsyncSession,
    ) -> Customer | None:
        customer = await self.get_customer(business_uid, customer_uid, session)
        if customer is None:
            return None
        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(customer, key, value)
        await session.commit()
        await session.refresh(customer)
        return customer

    async def delete_customer(
        self, business_uid: uuid.UUID, customer_uid: uuid.UUID, session: AsyncSession
    ) -> bool:
        customer = await self.get_customer(business_uid, customer_uid, session)
        if customer is None:
            return False
        await session.delete(customer)
        await session.commit()
        return True
