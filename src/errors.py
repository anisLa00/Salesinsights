"""Typed application exceptions and their HTTP handlers.

Each domain error is a small exception class; `register_all_errors` maps each
one to a JSON response with a stable `error_code`, so clients can branch on a
code rather than parsing messages.
"""

from typing import Any, Callable

from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


class SalesInsightException(Exception):
    """Base class for all application errors."""


# --- Auth ---
class InvalidToken(SalesInsightException):
    """The provided token is invalid or expired."""


class RevokedToken(SalesInsightException):
    """The provided token has been revoked (logged out)."""


class AccessTokenRequired(SalesInsightException):
    """A refresh token was supplied where an access token is required."""


class RefreshTokenRequired(SalesInsightException):
    """An access token was supplied where a refresh token is required."""


class UserAlreadyExists(SalesInsightException):
    """Sign-up used an email that already belongs to a user."""


class InvalidCredentials(SalesInsightException):
    """Wrong email or password at login."""


class InsufficientPermission(SalesInsightException):
    """The user lacks the role needed for this action."""


class UserNotFound(SalesInsightException):
    """No user matched the given identifier."""


class AccountNotVerified(SalesInsightException):
    """The account has not verified its email yet."""


# --- Domain ---
class ProductNotFound(SalesInsightException):
    """No product matched the given id."""


class CustomerNotFound(SalesInsightException):
    """No customer matched the given id."""


class SaleNotFound(SalesInsightException):
    """No sale matched the given id."""


def create_exception_handler(
    status_code: int, initial_detail: Any
) -> Callable[[Request, Exception], JSONResponse]:
    async def exception_handler(request: Request, exc: SalesInsightException):
        return JSONResponse(content=initial_detail, status_code=status_code)

    return exception_handler


def register_all_errors(app: FastAPI) -> None:
    handlers = {
        UserAlreadyExists: (
            status.HTTP_403_FORBIDDEN,
            {"message": "User with email already exists", "error_code": "user_exists"},
        ),
        UserNotFound: (
            status.HTTP_404_NOT_FOUND,
            {"message": "User not found", "error_code": "user_not_found"},
        ),
        InvalidCredentials: (
            status.HTTP_400_BAD_REQUEST,
            {
                "message": "Invalid email or password",
                "error_code": "invalid_email_or_password",
            },
        ),
        InvalidToken: (
            status.HTTP_401_UNAUTHORIZED,
            {
                "message": "Token is invalid or expired",
                "resolution": "Please get a new token",
                "error_code": "invalid_token",
            },
        ),
        RevokedToken: (
            status.HTTP_401_UNAUTHORIZED,
            {
                "message": "Token has been revoked",
                "resolution": "Please get a new token",
                "error_code": "token_revoked",
            },
        ),
        AccessTokenRequired: (
            status.HTTP_401_UNAUTHORIZED,
            {
                "message": "Please provide a valid access token",
                "error_code": "access_token_required",
            },
        ),
        RefreshTokenRequired: (
            status.HTTP_403_FORBIDDEN,
            {
                "message": "Please provide a valid refresh token",
                "error_code": "refresh_token_required",
            },
        ),
        InsufficientPermission: (
            status.HTTP_403_FORBIDDEN,
            {
                "message": "You do not have enough permissions to perform this action",
                "error_code": "insufficient_permissions",
            },
        ),
        AccountNotVerified: (
            status.HTTP_403_FORBIDDEN,
            {
                "message": "Account not verified",
                "resolution": "Please check your email for verification details",
                "error_code": "account_not_verified",
            },
        ),
        ProductNotFound: (
            status.HTTP_404_NOT_FOUND,
            {"message": "Product not found", "error_code": "product_not_found"},
        ),
        CustomerNotFound: (
            status.HTTP_404_NOT_FOUND,
            {"message": "Customer not found", "error_code": "customer_not_found"},
        ),
        SaleNotFound: (
            status.HTTP_404_NOT_FOUND,
            {"message": "Sale not found", "error_code": "sale_not_found"},
        ),
    }

    for exc_class, (status_code, detail) in handlers.items():
        app.add_exception_handler(
            exc_class, create_exception_handler(status_code, detail)
        )

    @app.exception_handler(500)
    async def internal_server_error(request, exc):
        return JSONResponse(
            content={"message": "Oops! Something went wrong", "error_code": "server_error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        print(str(exc))
        return JSONResponse(
            content={"message": "Oops! Something went wrong", "error_code": "server_error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
