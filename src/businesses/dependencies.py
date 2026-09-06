"""Reusable business authorization dependencies.

Every business-scoped route resolves a :class:`BusinessContext` through one of
the dependencies here. The context is only ever built after verifying that the
authenticated user holds an *active* membership in the business, so routes and
services never have to re-derive permissions — and a `business_uid` supplied by
the client is never trusted on its own.
"""

import uuid
from dataclasses import dataclass
from typing import Callable, Sequence

from fastapi import Depends
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.main import get_session
from src.db.models import Business, BusinessMember, BusinessRole, User
from src.errors import (
    AccountNotVerified,
    BusinessNotFound,
    InsufficientPermission,
    NoBusinessContext,
    NotBusinessMember,
)

# --- Role groups, so permissions are declared once and reused ------------
ROLE_OWNER = BusinessRole.OWNER.value
ROLE_ADMIN = BusinessRole.ADMIN.value
ROLE_MANAGER = BusinessRole.MANAGER.value
ROLE_EMPLOYEE = BusinessRole.EMPLOYEE.value

#: Change business settings.
MANAGE_BUSINESS = (ROLE_OWNER, ROLE_ADMIN)
#: Invite/update/remove teammates.
MANAGE_MEMBERS = (ROLE_OWNER, ROLE_ADMIN)
#: Create/update/delete products and customers.
MANAGE_CATALOG = (ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER)
#: View analytics, insights and the dashboard.
VIEW_ANALYTICS = (ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER)
#: Everyone who can operate day to day (record sales, read catalog).
ANY_MEMBER = (ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE)


@dataclass
class BusinessContext:
    """A verified (user, business, membership) triple."""

    business: Business
    member: BusinessMember
    user: User

    @property
    def business_uid(self) -> uuid.UUID:
        return self.business.uid

    @property
    def role(self) -> str:
        return self.member.role

    def has_role(self, roles: Sequence[str]) -> bool:
        return self.role in roles


async def _build_context(
    business_uid: uuid.UUID, user: User, session: AsyncSession
) -> BusinessContext:
    if not user.is_verified:
        raise AccountNotVerified()

    business = (
        await session.exec(select(Business).where(Business.uid == business_uid))
    ).first()
    if business is None:
        raise BusinessNotFound()

    member = (
        await session.exec(
            select(BusinessMember).where(
                BusinessMember.business_uid == business_uid,
                BusinessMember.user_uid == user.uid,
            )
        )
    ).first()

    # A non-member and an inactive member are treated identically, and the
    # business is reported as "not yours" rather than "does not exist" only
    # after we know it exists — outsiders never learn either way.
    if member is None or not member.is_active:
        raise NotBusinessMember()

    return BusinessContext(business=business, member=member, user=user)


async def business_context_from_path(
    business_uid: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BusinessContext:
    """Resolve business context from the `{business_uid}` path parameter."""
    return await _build_context(business_uid, user, session)


async def default_business_context(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BusinessContext:
    """Resolve the caller's default business.

    Backs the legacy, non-nested routes (`/api/v1/products/` etc.) so they keep
    working after the multi-tenancy upgrade. Prefers a business the user owns,
    otherwise their oldest active membership.
    """
    if not user.is_verified:
        raise AccountNotVerified()

    statement = (
        select(Business, BusinessMember)
        .join(BusinessMember, BusinessMember.business_uid == Business.uid)
        .where(
            BusinessMember.user_uid == user.uid,
            BusinessMember.is_active == True,  # noqa: E712
        )
        .order_by(desc(Business.owner_uid == user.uid), BusinessMember.joined_at)
    )
    row = (await session.exec(statement)).first()
    if row is None:
        raise NoBusinessContext()

    business, member = row
    return BusinessContext(business=business, member=member, user=user)


def require_business_role(
    roles: Sequence[str],
    context_dependency: Callable = business_context_from_path,
) -> Callable:
    """Build a dependency that requires one of ``roles`` in the business.

    Usage::

        ctx: BusinessContext = Depends(
            require_business_role(MANAGE_MEMBERS, business_context_from_path)
        )

    The context dependency is a parameter so the same route handlers can be
    mounted both business-scoped (`/businesses/{business_uid}/...`) and on the
    legacy default-business paths without duplicating permission logic.
    """

    async def dependency(
        context: BusinessContext = Depends(context_dependency),
    ) -> BusinessContext:
        if not context.has_role(roles):
            raise InsufficientPermission()
        return context

    return dependency


def require_business_member(
    context_dependency: Callable = business_context_from_path,
) -> Callable:
    """Dependency requiring only an active membership (any role)."""
    return require_business_role(ANY_MEMBER, context_dependency)
