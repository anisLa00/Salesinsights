"""Business, membership, and invitation routes."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import get_current_user
from src.celery import send_email
from src.config import Config
from src.db.main import get_session
from src.db.models import BusinessRole, User
from src.errors import AccountNotVerified, CannotModifyOwner

from .dependencies import (
    ANY_MEMBER,
    MANAGE_BUSINESS,
    MANAGE_MEMBERS,
    BusinessContext,
    business_context_from_path,
    require_business_role,
)
from .schemas import (
    BusinessCreateModel,
    BusinessMemberModel,
    BusinessModel,
    BusinessUpdateModel,
    BusinessWithRoleModel,
    InvitationAcceptModel,
    InvitationCreatedModel,
    InvitationCreateModel,
    InvitationModel,
    MemberUpdateModel,
    MemberUserModel,
)
from .service import BusinessService, get_member_or_404

business_router = APIRouter()
business_service = BusinessService()


def _accept_url(token: str) -> str:
    return f"http://{Config.DOMAIN}/api/v1/businesses/invitations/accept?token={token}"


def _member_response(member, user: User | None = None) -> BusinessMemberModel:
    """Build a member response without touching ORM relationships.

    Reading `member.user` would trigger a lazy load, which raises
    MissingGreenlet under the async session — so the related user is always
    passed in explicitly by the caller.
    """
    return BusinessMemberModel(
        uid=member.uid,
        business_uid=member.business_uid,
        user_uid=member.user_uid,
        role=member.role,
        is_active=member.is_active,
        joined_at=member.joined_at,
        user=(
            MemberUserModel(
                uid=user.uid,
                username=user.username,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            if user is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Invitation acceptance — declared first so the literal path is never shadowed
# by /{business_uid}. Requires a logged-in user, but not membership.
# ---------------------------------------------------------------------------
@business_router.post("/invitations/accept", response_model=BusinessMemberModel)
async def accept_invitation(
    data: InvitationAcceptModel,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Redeem a signed invitation token and join the business."""
    if not user.is_verified:
        raise AccountNotVerified()
    member = await business_service.accept_invitation(data.token, user, session)
    return _member_response(member, user)


# ---------------------------------------------------------------------------
# Businesses
# ---------------------------------------------------------------------------
@business_router.post(
    "/", status_code=status.HTTP_201_CREATED, response_model=BusinessModel
)
async def create_business(
    data: BusinessCreateModel,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a business; the caller becomes its owner and first member."""
    if not user.is_verified:
        raise AccountNotVerified()
    return await business_service.create_business(data, user, session)


@business_router.get("/", response_model=List[BusinessWithRoleModel])
async def list_my_businesses(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List every business the caller is an active member of."""
    rows = await business_service.list_businesses_for_user(user.uid, session)
    return [
        BusinessWithRoleModel(
            uid=business.uid,
            name=business.name,
            owner_uid=business.owner_uid,
            created_at=business.created_at,
            updated_at=business.updated_at,
            role=role,
        )
        for business, role in rows
    ]


@business_router.get("/{business_uid}", response_model=BusinessWithRoleModel)
async def get_business(
    ctx: BusinessContext = Depends(require_business_role(ANY_MEMBER)),
):
    return BusinessWithRoleModel(
        uid=ctx.business.uid,
        name=ctx.business.name,
        owner_uid=ctx.business.owner_uid,
        created_at=ctx.business.created_at,
        updated_at=ctx.business.updated_at,
        role=ctx.role,
    )


@business_router.patch("/{business_uid}", response_model=BusinessModel)
async def update_business(
    data: BusinessUpdateModel,
    ctx: BusinessContext = Depends(require_business_role(MANAGE_BUSINESS)),
    session: AsyncSession = Depends(get_session),
):
    return await business_service.update_business(ctx.business, data, session)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
@business_router.get(
    "/{business_uid}/members", response_model=List[BusinessMemberModel]
)
async def list_members(
    ctx: BusinessContext = Depends(require_business_role(ANY_MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    rows = await business_service.list_members(ctx.business_uid, session)
    return [_member_response(member, user) for member, user in rows]


@business_router.post(
    "/{business_uid}/members/invite",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitationCreatedModel,
)
async def invite_member(
    data: InvitationCreateModel,
    ctx: BusinessContext = Depends(require_business_role(MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
):
    """Invite someone by email.

    Works whether or not they already have an account: the signed token is
    emailed through the existing Celery task, and they redeem it once their
    account exists and is verified.
    """
    if data.role == BusinessRole.OWNER:
        raise CannotModifyOwner()

    invitation, token = await business_service.create_business_invitation(
        ctx.business_uid, data, ctx.user, session
    )

    link = _accept_url(token)
    html = (
        f"<h1>You've been invited to {ctx.business.name}</h1>"
        f"<p>{ctx.user.first_name} invited you to join "
        f"<b>{ctx.business.name}</b> on Sales Insight as "
        f"<b>{invitation.role}</b>.</p>"
        f'<p>Accept the invitation <a href="{link}">here</a>. '
        f"If you don't have an account yet, sign up with this email address "
        f"first, verify it, then open the link again.</p>"
    )
    send_email.delay([invitation.email], f"Invitation to {ctx.business.name}", html)

    return InvitationCreatedModel(
        invitation=InvitationModel.model_validate(invitation, from_attributes=True),
        invite_token=token,
        accept_url=link,
    )


@business_router.get(
    "/{business_uid}/invitations", response_model=List[InvitationModel]
)
async def list_invitations(
    ctx: BusinessContext = Depends(require_business_role(MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
):
    return await business_service.list_invitations(ctx.business_uid, session)


@business_router.delete(
    "/{business_uid}/invitations/{invitation_uid}", response_model=InvitationModel
)
async def revoke_invitation(
    invitation_uid: uuid.UUID,
    ctx: BusinessContext = Depends(require_business_role(MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
):
    return await business_service.revoke_invitation(
        ctx.business_uid, invitation_uid, session
    )


@business_router.patch(
    "/{business_uid}/members/{member_uid}", response_model=BusinessMemberModel
)
async def update_member(
    member_uid: uuid.UUID,
    data: MemberUpdateModel,
    ctx: BusinessContext = Depends(require_business_role(MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
):
    """Change a teammate's role or deactivate them.

    The owner's membership is immutable here, and nobody can be promoted to
    owner through this endpoint.
    """
    member = await get_member_or_404(ctx.business_uid, member_uid, session)

    if member.role == BusinessRole.OWNER.value:
        raise CannotModifyOwner()
    if data.role == BusinessRole.OWNER:
        raise CannotModifyOwner()

    changes = {
        key: (value.value if isinstance(value, BusinessRole) else value)
        for key, value in data.model_dump(exclude_unset=True).items()
        if value is not None
    }
    updated = await business_service.update_member(member, changes, session)
    member_user = await session.get(User, updated.user_uid)
    return _member_response(updated, member_user)


@business_router.delete(
    "/{business_uid}/members/{member_uid}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    member_uid: uuid.UUID,
    ctx: BusinessContext = Depends(require_business_role(MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
):
    member = await get_member_or_404(ctx.business_uid, member_uid, session)
    if member.role == BusinessRole.OWNER.value:
        raise CannotModifyOwner()
    await business_service.remove_member(member, session)
    return None
