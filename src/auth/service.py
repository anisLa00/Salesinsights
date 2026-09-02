"""Database operations for users."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import User

from .schemas import UserCreateModel
from .utils import generate_passwd_hash


class UserService:
    async def get_user_by_email(self, email: str, session: AsyncSession) -> User | None:
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        return result.first()

    async def user_exists(self, email: str, session: AsyncSession) -> bool:
        user = await self.get_user_by_email(email, session)
        return user is not None

    async def create_user(
        self, user_data: UserCreateModel, session: AsyncSession
    ) -> User:
        data = user_data.model_dump()
        password = data.pop("password")
        new_user = User(**data)
        new_user.password_hash = generate_passwd_hash(password)
        new_user.role = "user"
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user

    async def update_user(
        self, user: User, user_data: dict, session: AsyncSession
    ) -> User:
        for key, value in user_data.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user
