"""Customer CRUD routes, built once and mounted twice.

See `src/products/routes.py` for why this is a factory.
"""

import uuid
from typing import Callable, List

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.businesses.dependencies import (
    ANY_MEMBER,
    MANAGE_CATALOG,
    BusinessContext,
    business_context_from_path,
    require_business_role,
)
from src.db.main import get_session
from src.errors import CustomerNotFound

from .schemas import CustomerCreateModel, CustomerModel, CustomerUpdateModel
from .service import CustomerService

customer_service = CustomerService()


def build_customer_router(
    context_dependency: Callable = business_context_from_path,
) -> APIRouter:
    router = APIRouter()

    read_ctx = require_business_role(ANY_MEMBER, context_dependency)
    write_ctx = require_business_role(MANAGE_CATALOG, context_dependency)

    @router.get("/", response_model=List[CustomerModel])
    async def get_all_customers(
        ctx: BusinessContext = Depends(read_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        return await customer_service.get_all_customers(ctx.business_uid, session)

    @router.post(
        "/", status_code=status.HTTP_201_CREATED, response_model=CustomerModel
    )
    async def create_customer(
        customer_data: CustomerCreateModel,
        ctx: BusinessContext = Depends(write_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        return await customer_service.create_customer(
            ctx.business_uid, customer_data, session
        )

    @router.get("/{customer_uid}", response_model=CustomerModel)
    async def get_customer(
        customer_uid: uuid.UUID,
        ctx: BusinessContext = Depends(read_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        customer = await customer_service.get_customer(
            ctx.business_uid, customer_uid, session
        )
        if customer is None:
            raise CustomerNotFound()
        return customer

    @router.patch("/{customer_uid}", response_model=CustomerModel)
    async def update_customer(
        customer_uid: uuid.UUID,
        update_data: CustomerUpdateModel,
        ctx: BusinessContext = Depends(write_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        updated = await customer_service.update_customer(
            ctx.business_uid, customer_uid, update_data, session
        )
        if updated is None:
            raise CustomerNotFound()
        return updated

    @router.delete("/{customer_uid}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_customer(
        customer_uid: uuid.UUID,
        ctx: BusinessContext = Depends(write_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        deleted = await customer_service.delete_customer(
            ctx.business_uid, customer_uid, session
        )
        if not deleted:
            raise CustomerNotFound()
        return None

    return router
