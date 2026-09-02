"""Sales routes: record and browse sales (all require a valid access token)."""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import AccessTokenBearer, RoleChecker
from src.db.main import get_session
from src.errors import SaleNotFound

from .schemas import SaleCreateModel, SaleDetailModel, SaleModel
from .service import SaleService

sale_router = APIRouter()
sale_service = SaleService()
access_token_bearer = AccessTokenBearer()
role_checker = Depends(RoleChecker(["admin", "user"]))


@sale_router.get("/", response_model=List[SaleDetailModel], dependencies=[role_checker])
async def get_all_sales(
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    return await sale_service.get_all_sales(session)


@sale_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SaleModel,
    dependencies=[role_checker],
)
async def create_sale(
    sale_data: SaleCreateModel,
    session: AsyncSession = Depends(get_session),
    token_details: dict = Depends(access_token_bearer),
):
    user_uid = token_details["user"]["user_uid"]
    return await sale_service.create_sale(sale_data, user_uid, session)


@sale_router.get(
    "/{sale_uid}", response_model=SaleDetailModel, dependencies=[role_checker]
)
async def get_sale(
    sale_uid: str,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    sale = await sale_service.get_sale(sale_uid, session)
    if sale is None:
        raise SaleNotFound()
    return sale


@sale_router.delete(
    "/{sale_uid}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[role_checker],
)
async def delete_sale(
    sale_uid: str,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    deleted = await sale_service.delete_sale(sale_uid, session)
    if not deleted:
        raise SaleNotFound()
    return None
