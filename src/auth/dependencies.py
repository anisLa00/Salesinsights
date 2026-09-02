"""Auth dependencies: bearer-token guards, current user, and role checks."""

from typing import List

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.main import get_session
from src.db.models import User
from src.db.redis import token_in_blocklist
from src.errors import (
    AccessTokenRequired,
    AccountNotVerified,
    InsufficientPermission,
    InvalidToken,
    RefreshTokenRequired,
)

from .service import UserService
from .utils import decode_token

user_service = UserService()


class TokenBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> dict:
        creds: HTTPAuthorizationCredentials = await super().__call__(request)
        token = creds.credentials
        token_data = decode_token(token)

        if token_data is None:
            raise InvalidToken()

        if await token_in_blocklist(token_data["jti"]):
            raise InvalidToken()

        self.verify_token_data(token_data)
        return token_data

    def verify_token_data(self, token_data: dict) -> None:
        raise NotImplementedError("Override this method in a subclass")


class AccessTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict) -> None:
        if token_data and token_data["refresh"]:
            raise AccessTokenRequired()


class RefreshTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict) -> None:
        if token_data and not token_data["refresh"]:
            raise RefreshTokenRequired()


async def get_current_user(
    token_details: dict = Depends(AccessTokenBearer()),
    session: AsyncSession = Depends(get_session),
) -> User:
    user_email = token_details["user"]["email"]
    return await user_service.get_user_by_email(user_email, session)


class RoleChecker:
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> bool:
        if not current_user.is_verified:
            raise AccountNotVerified()
        if current_user.role in self.allowed_roles:
            return True
        raise InsufficientPermission()
