"""Customer CRUD routes (all require a valid access token)."""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import AccessTokenBearer, RoleChecker
from src.db.main import get_session
from src.errors import CustomerNotFound

from .schemas import CustomerCreateModel, CustomerModel, CustomerUpdateModel
from .service import CustomerService

customer_router = APIRouter()
customer_service = CustomerService()
access_token_bearer = AccessTokenBearer()
role_checker = Depends(RoleChecker(["admin", "user"]))


@customer_router.get(
    "/", response_model=List[CustomerModel], dependencies=[role_checker]
)
async def get_all_customers(
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    return await customer_service.get_all_customers(session)


@customer_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=CustomerModel,
    dependencies=[role_checker],
)
async def create_customer(
    customer_data: CustomerCreateModel,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    return await customer_service.create_customer(customer_data, session)


@customer_router.get(
    "/{customer_uid}", response_model=CustomerModel, dependencies=[role_checker]
)
async def get_customer(
    customer_uid: str,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    customer = await customer_service.get_customer(customer_uid, session)
    if customer is None:
        raise CustomerNotFound()
    return customer


@customer_router.patch(
    "/{customer_uid}", response_model=CustomerModel, dependencies=[role_checker]
)
async def update_customer(
    customer_uid: str,
    update_data: CustomerUpdateModel,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    updated = await customer_service.update_customer(customer_uid, update_data, session)
    if updated is None:
        raise CustomerNotFound()
    return updated


@customer_router.delete(
    "/{customer_uid}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[role_checker],
)
async def delete_customer(
    customer_uid: str,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    deleted = await customer_service.delete_customer(customer_uid, session)
    if not deleted:
        raise CustomerNotFound()
    return None
