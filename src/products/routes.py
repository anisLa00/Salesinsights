"""Product CRUD routes (all require a valid access token)."""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import AccessTokenBearer, RoleChecker
from src.db.main import get_session
from src.errors import ProductNotFound

from .schemas import ProductCreateModel, ProductModel, ProductUpdateModel
from .service import ProductService

product_router = APIRouter()
product_service = ProductService()
access_token_bearer = AccessTokenBearer()
role_checker = Depends(RoleChecker(["admin", "user"]))


@product_router.get("/", response_model=List[ProductModel], dependencies=[role_checker])
async def get_all_products(
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    return await product_service.get_all_products(session)


@product_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductModel,
    dependencies=[role_checker],
)
async def create_product(
    product_data: ProductCreateModel,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    return await product_service.create_product(product_data, session)


@product_router.get(
    "/{product_uid}", response_model=ProductModel, dependencies=[role_checker]
)
async def get_product(
    product_uid: str,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    product = await product_service.get_product(product_uid, session)
    if product is None:
        raise ProductNotFound()
    return product


@product_router.patch(
    "/{product_uid}", response_model=ProductModel, dependencies=[role_checker]
)
async def update_product(
    product_uid: str,
    update_data: ProductUpdateModel,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    updated = await product_service.update_product(product_uid, update_data, session)
    if updated is None:
        raise ProductNotFound()
    return updated


@product_router.delete(
    "/{product_uid}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[role_checker],
)
async def delete_product(
    product_uid: str,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    deleted = await product_service.delete_product(product_uid, session)
    if not deleted:
        raise ProductNotFound()
    return None
