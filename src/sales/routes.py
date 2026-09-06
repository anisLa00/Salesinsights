"""Sales routes, built once and mounted twice.

Recording a sale is available to every active member (including employees);
deleting one is restricted to manager and above.
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
from src.errors import SaleNotFound

from .schemas import SaleCreateModel, SaleDetailModel, SaleModel
from .service import SaleService

sale_service = SaleService()


def build_sale_router(
    context_dependency: Callable = business_context_from_path,
) -> APIRouter:
    router = APIRouter()

    member_ctx = require_business_role(ANY_MEMBER, context_dependency)
    manage_ctx = require_business_role(MANAGE_CATALOG, context_dependency)

    @router.get("/", response_model=List[SaleDetailModel])
    async def get_all_sales(
        ctx: BusinessContext = Depends(member_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        return await sale_service.get_all_sales(ctx.business_uid, session)

    @router.post("/", status_code=status.HTTP_201_CREATED, response_model=SaleModel)
    async def create_sale(
        sale_data: SaleCreateModel,
        ctx: BusinessContext = Depends(member_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        """Record a sale.

        The business comes from the verified context and the employee from the
        authenticated user — neither is read from the request body.
        """
        return await sale_service.create_sale(
            ctx.business_uid, ctx.user.uid, sale_data, session
        )

    @router.get("/{sale_uid}", response_model=SaleDetailModel)
    async def get_sale(
        sale_uid: uuid.UUID,
        ctx: BusinessContext = Depends(member_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        sale = await sale_service.get_sale(ctx.business_uid, sale_uid, session)
        if sale is None:
            raise SaleNotFound()
        return sale

    @router.delete("/{sale_uid}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_sale(
        sale_uid: uuid.UUID,
        ctx: BusinessContext = Depends(manage_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        deleted = await sale_service.delete_sale(ctx.business_uid, sale_uid, session)
        if not deleted:
            raise SaleNotFound()
        return None

    return router
