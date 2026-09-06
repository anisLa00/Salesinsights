"""Product CRUD routes, built once and mounted twice.

`build_product_router` takes the dependency that resolves the business
context, so the exact same handlers serve both the canonical business-scoped
paths (`/businesses/{business_uid}/products`) and the legacy flat paths
(`/products`, which resolve the caller's default business). No handler logic
is duplicated between the two mounts.
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
from src.errors import ProductNotFound

from .schemas import ProductCreateModel, ProductModel, ProductUpdateModel
from .service import ProductService

product_service = ProductService()


def build_product_router(
    context_dependency: Callable = business_context_from_path,
) -> APIRouter:
    router = APIRouter()

    # Reading the catalog is operational: every active member needs it to
    # record a sale. Changing it is restricted to manager and above.
    read_ctx = require_business_role(ANY_MEMBER, context_dependency)
    write_ctx = require_business_role(MANAGE_CATALOG, context_dependency)

    @router.get("/", response_model=List[ProductModel])
    async def get_all_products(
        ctx: BusinessContext = Depends(read_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        return await product_service.get_all_products(ctx.business_uid, session)

    @router.post(
        "/", status_code=status.HTTP_201_CREATED, response_model=ProductModel
    )
    async def create_product(
        product_data: ProductCreateModel,
        ctx: BusinessContext = Depends(write_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        return await product_service.create_product(
            ctx.business_uid, product_data, session
        )

    @router.get("/{product_uid}", response_model=ProductModel)
    async def get_product(
        product_uid: uuid.UUID,
        ctx: BusinessContext = Depends(read_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        product = await product_service.get_product(
            ctx.business_uid, product_uid, session
        )
        if product is None:
            raise ProductNotFound()
        return product

    @router.patch("/{product_uid}", response_model=ProductModel)
    async def update_product(
        product_uid: uuid.UUID,
        update_data: ProductUpdateModel,
        ctx: BusinessContext = Depends(write_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        updated = await product_service.update_product(
            ctx.business_uid, product_uid, update_data, session
        )
        if updated is None:
            raise ProductNotFound()
        return updated

    @router.delete("/{product_uid}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_product(
        product_uid: uuid.UUID,
        ctx: BusinessContext = Depends(write_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        deleted = await product_service.delete_product(
            ctx.business_uid, product_uid, session
        )
        if not deleted:
            raise ProductNotFound()
        return None

    return router
