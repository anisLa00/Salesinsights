"""Authentication routes: signup, email verification, login, tokens, reset."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.celery import send_email
from src.config import Config
from src.db.main import get_session
from src.db.redis import add_jti_to_blocklist
from src.errors import (
    InvalidCredentials,
    InvalidToken,
    UserAlreadyExists,
    UserNotFound,
)

from .dependencies import (
    AccessTokenBearer,
    RefreshTokenBearer,
    RoleChecker,
    get_current_user,
)
from .schemas import (
    PasswordResetConfirmModel,
    PasswordResetRequestModel,
    UserCreateModel,
    UserLoginModel,
    UserModel,
)
from .service import UserService
from .utils import (
    create_access_token,
    create_url_safe_token,
    decode_url_safe_token,
    generate_passwd_hash,
    verify_password,
)

auth_router = APIRouter()
user_service = UserService()
role_checker = RoleChecker(["admin", "user"])

REFRESH_TOKEN_EXPIRY_DAYS = 2


def _verification_link(token: str) -> str:
    return f"http://{Config.DOMAIN}/api/v1/auth/verify/{token}"


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def create_user_account(
    user_data: UserCreateModel, session: AsyncSession = Depends(get_session)
):
    email = user_data.email

    if await user_service.user_exists(email, session):
        raise UserAlreadyExists()

    new_user = await user_service.create_user(user_data, session)

    token = create_url_safe_token({"email": email})
    html = (
        "<h1>Verify your email</h1>"
        f'<p>Click <a href="{_verification_link(token)}">here</a> to verify '
        "your Sales Insight account.</p>"
    )
    send_email.delay([email], "Verify your email", html)

    return {
        "message": "Account created! Check your email to verify your account.",
        "user": UserModel.model_validate(new_user, from_attributes=True),
    }


@auth_router.get("/verify/{token}")
async def verify_user_account(
    token: str, session: AsyncSession = Depends(get_session)
):
    token_data = decode_url_safe_token(token)
    if token_data is None:
        return JSONResponse(status_code=400, content={"message": "Invalid token"})

    user_email = token_data.get("email")
    if not user_email:
        raise InvalidToken()

    user = await user_service.get_user_by_email(user_email, session)
    if not user:
        raise UserNotFound()

    await user_service.update_user(user, {"is_verified": True}, session)
    return JSONResponse(
        content={"message": "Account verified successfully"},
        status_code=status.HTTP_200_OK,
    )


@auth_router.post("/resend-verification")
async def resend_verification(
    data: PasswordResetRequestModel, session: AsyncSession = Depends(get_session)
):
    user = await user_service.get_user_by_email(data.email, session)
    if not user:
        raise UserNotFound()
    if user.is_verified:
        return {"message": "Account is already verified"}

    if user.verification_email_sent_at:
        elapsed = datetime.now() - user.verification_email_sent_at
        if elapsed < timedelta(minutes=1):
            return {"message": "Please wait 1 minute before requesting another email"}

    token = create_url_safe_token({"email": user.email})
    html = (
        "<h1>Verify your email</h1>"
        f'<p>Click <a href="{_verification_link(token)}">here</a> to verify.</p>'
    )
    send_email.delay([user.email], "Verify your email", html)
    await user_service.update_user(
        user, {"verification_email_sent_at": datetime.now()}, session
    )
    return {"message": "Verification email sent. Please check your inbox."}


@auth_router.post("/login")
async def login(
    login_data: UserLoginModel, session: AsyncSession = Depends(get_session)
):
    user = await user_service.get_user_by_email(login_data.email, session)
    if user is not None and verify_password(login_data.password, user.password_hash):
        access_token = create_access_token(
            user_data={
                "email": user.email,
                "user_uid": str(user.uid),
                "role": user.role,
            }
        )
        refresh_token = create_access_token(
            user_data={"email": user.email, "user_uid": str(user.uid)},
            refresh=True,
            expiry=timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        )
        return JSONResponse(
            content={
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {"email": user.email, "uid": str(user.uid)},
            }
        )
    raise InvalidCredentials()


@auth_router.get("/refresh-token")
async def get_new_access_token(
    token_details: dict = Depends(RefreshTokenBearer()),
):
    expiry_timestamp = token_details["exp"]
    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(user_data=token_details["user"])
        return JSONResponse(content={"access_token": new_access_token})
    raise InvalidToken()


@auth_router.get("/logout")
async def revoke_token(token_details: dict = Depends(AccessTokenBearer())):
    await add_jti_to_blocklist(token_details["jti"])
    return JSONResponse(
        content={"message": "Logged out successfully"},
        status_code=status.HTTP_200_OK,
    )


@auth_router.get("/me", response_model=UserModel)
async def get_me(
    user=Depends(get_current_user), _: bool = Depends(role_checker)
):
    return user


@auth_router.post("/password-reset-request")
async def password_reset_request(data: PasswordResetRequestModel):
    token = create_url_safe_token({"email": data.email})
    link = f"http://{Config.DOMAIN}/api/v1/auth/password-reset-confirm/{token}"
    html = (
        "<h1>Reset your password</h1>"
        f'<p>Click <a href="{link}">here</a> to reset your password.</p>'
    )
    send_email.delay([data.email], "Reset your password", html)
    return JSONResponse(
        content={"message": "Check your email for password-reset instructions."},
        status_code=status.HTTP_200_OK,
    )


@auth_router.post("/password-reset-confirm/{token}")
async def password_reset_confirm(
    token: str,
    passwords: PasswordResetConfirmModel,
    session: AsyncSession = Depends(get_session),
):
    if passwords.new_password != passwords.confirm_new_password:
        raise HTTPException(
            detail="Passwords do not match", status_code=status.HTTP_400_BAD_REQUEST
        )

    token_data = decode_url_safe_token(token)
    if token_data is None or not token_data.get("email"):
        raise InvalidToken()

    user = await user_service.get_user_by_email(token_data["email"], session)
    if not user:
        raise UserNotFound()

    await user_service.update_user(
        user, {"password_hash": generate_passwd_hash(passwords.new_password)}, session
    )
    return JSONResponse(
        content={"message": "Password has been updated"},
        status_code=status.HTTP_200_OK,
    )
