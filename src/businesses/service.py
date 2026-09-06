"""Database operations for businesses, members, and invitations.

Route -> Service -> Database, same as every other module. All tenant scoping
lives here: callers pass a `business_uid` that the dependency layer has
already verified the user belongs to.
"""

import uuid
from datetime import datetime, timedelta

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import Config
from src.db.models import (
    Business,
    BusinessInvitation,
    BusinessMember,
    BusinessRole,
    InvitationStatus,
    User,
)
from src.errors import (
    AlreadyBusinessMember,
    BusinessNotFound,
    InvitationInvalid,
    InvitationNotFound,
    MemberNotFound,
)

from .schemas import BusinessCreateModel, BusinessUpdateModel, InvitationCreateModel

# Invitations are signed with their own salt so an invite token can never be
# replayed as an email-verification or password-reset token.
INVITATION_SALT = "business-invitation"
INVITATION_TTL_DAYS = 7

_serializer = URLSafeTimedSerializer(
    secret_key=Config.JWT_SECRET, salt=INVITATION_SALT
)


def create_invitation_token(data: dict) -> str:
    return _serializer.dumps(data)


def decode_invitation_token(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=INVITATION_TTL_DAYS * 24 * 3600)
    except (SignatureExpired, BadSignature):
        return None


class BusinessService:
    # ------------------------------------------------------------------
    # Businesses
    # ------------------------------------------------------------------
    async def create_business(
        self, data: BusinessCreateModel, owner: User, session: AsyncSession
    ) -> Business:
        """Create a business and make the creator its owner-member."""
        business = Business(name=data.name, owner_uid=owner.uid)
        session.add(business)
        await session.commit()
        await session.refresh(business)

        membership = BusinessMember(
            business_uid=business.uid,
            user_uid=owner.uid,
            role=BusinessRole.OWNER.value,
            is_active=True,
        )
        session.add(membership)
        await session.commit()
        await session.refresh(business)
        return business

    async def get_business(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> Business | None:
        statement = select(Business).where(Business.uid == business_uid)
        return (await session.exec(statement)).first()

    async def list_businesses_for_user(
        self, user_uid: uuid.UUID, session: AsyncSession
    ) -> list[tuple[Business, str]]:
        """Return (business, role) for every active membership of the user."""
        statement = (
            select(Business, BusinessMember.role)
            .join(BusinessMember, BusinessMember.business_uid == Business.uid)
            .where(
                BusinessMember.user_uid == user_uid,
                BusinessMember.is_active == True,  # noqa: E712
            )
            .order_by(desc(Business.created_at))
        )
        return list((await session.exec(statement)).all())

    async def update_business(
        self,
        business: Business,
        data: BusinessUpdateModel,
        session: AsyncSession,
    ) -> Business:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(business, key, value)
        business.updated_at = datetime.now()
        await session.commit()
        await session.refresh(business)
        return business

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------
    async def get_membership(
        self, business_uid: uuid.UUID, user_uid: uuid.UUID, session: AsyncSession
    ) -> BusinessMember | None:
        statement = select(BusinessMember).where(
            BusinessMember.business_uid == business_uid,
            BusinessMember.user_uid == user_uid,
        )
        return (await session.exec(statement)).first()

    async def list_members(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> list[tuple[BusinessMember, User]]:
        statement = (
            select(BusinessMember, User)
            .join(User, User.uid == BusinessMember.user_uid)
            .where(BusinessMember.business_uid == business_uid)
            .order_by(BusinessMember.joined_at)
        )
        return list((await session.exec(statement)).all())

    async def get_member(
        self, business_uid: uuid.UUID, member_uid: uuid.UUID, session: AsyncSession
    ) -> BusinessMember | None:
        """Look a member up *within* a business — never by id alone."""
        statement = select(BusinessMember).where(
            BusinessMember.uid == member_uid,
            BusinessMember.business_uid == business_uid,
        )
        return (await session.exec(statement)).first()

    async def add_member(
        self,
        business_uid: uuid.UUID,
        user_uid: uuid.UUID,
        role: str,
        session: AsyncSession,
    ) -> BusinessMember:
        existing = await self.get_membership(business_uid, user_uid, session)
        if existing is not None:
            if existing.is_active:
                raise AlreadyBusinessMember()
            # Re-activate a previously removed member instead of duplicating.
            existing.is_active = True
            existing.role = role
            await session.commit()
            await session.refresh(existing)
            return existing

        member = BusinessMember(
            business_uid=business_uid,
            user_uid=user_uid,
            role=role,
            is_active=True,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        return member

    async def update_member(
        self, member: BusinessMember, data: dict, session: AsyncSession
    ) -> BusinessMember:
        for key, value in data.items():
            setattr(member, key, value)
        await session.commit()
        await session.refresh(member)
        return member

    async def remove_member(
        self, member: BusinessMember, session: AsyncSession
    ) -> None:
        await session.delete(member)
        await session.commit()

    # ------------------------------------------------------------------
    # Invitations
    # ------------------------------------------------------------------
    async def create_business_invitation(
        self,
        business_uid: uuid.UUID,
        data: InvitationCreateModel,
        invited_by: User,
        session: AsyncSession,
    ) -> tuple[BusinessInvitation, str]:
        """Create a pending invitation and its signed token."""
        email = data.email.strip().lower()

        # If they already belong to this business, don't invite again.
        user_stmt = select(User).where(User.email == email)
        existing_user = (await session.exec(user_stmt)).first()
        if existing_user is not None:
            membership = await self.get_membership(
                business_uid, existing_user.uid, session
            )
            if membership is not None and membership.is_active:
                raise AlreadyBusinessMember()

        # Supersede any earlier pending invite for the same address.
        pending_stmt = select(BusinessInvitation).where(
            BusinessInvitation.business_uid == business_uid,
            BusinessInvitation.email == email,
            BusinessInvitation.status == InvitationStatus.PENDING.value,
        )
        for stale in (await session.exec(pending_stmt)).all():
            stale.status = InvitationStatus.REVOKED.value

        invitation = BusinessInvitation(
            business_uid=business_uid,
            email=email,
            role=data.role.value,
            status=InvitationStatus.PENDING.value,
            invited_by_uid=invited_by.uid,
            expires_at=datetime.now() + timedelta(days=INVITATION_TTL_DAYS),
        )
        session.add(invitation)
        await session.commit()
        await session.refresh(invitation)

        token = create_invitation_token(
            {
                "invitation_uid": str(invitation.uid),
                "business_uid": str(business_uid),
                "email": email,
            }
        )
        return invitation, token

    async def list_invitations(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> list[BusinessInvitation]:
        statement = (
            select(BusinessInvitation)
            .where(BusinessInvitation.business_uid == business_uid)
            .order_by(desc(BusinessInvitation.created_at))
        )
        return list((await session.exec(statement)).all())

    async def accept_invitation(
        self, token: str, user: User, session: AsyncSession
    ) -> BusinessMember:
        """Validate a signed token and turn it into an active membership."""
        payload = decode_invitation_token(token)
        if payload is None:
            raise InvitationInvalid()

        statement = select(BusinessInvitation).where(
            BusinessInvitation.uid == uuid.UUID(payload["invitation_uid"])
        )
        invitation = (await session.exec(statement)).first()
        if invitation is None:
            raise InvitationNotFound()

        if (
            invitation.status != InvitationStatus.PENDING.value
            or invitation.expires_at < datetime.now()
        ):
            raise InvitationInvalid()

        # The token is bound to an address: don't let it be redeemed by
        # whoever happens to be logged in.
        if user.email.strip().lower() != invitation.email:
            raise InvitationInvalid()

        member = await self.add_member(
            invitation.business_uid, user.uid, invitation.role, session
        )

        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.now()
        await session.commit()
        await session.refresh(member)
        return member

    async def revoke_invitation(
        self, business_uid: uuid.UUID, invitation_uid: uuid.UUID, session: AsyncSession
    ) -> BusinessInvitation:
        statement = select(BusinessInvitation).where(
            BusinessInvitation.uid == invitation_uid,
            BusinessInvitation.business_uid == business_uid,
        )
        invitation = (await session.exec(statement)).first()
        if invitation is None:
            raise InvitationNotFound()
        invitation.status = InvitationStatus.REVOKED.value
        await session.commit()
        await session.refresh(invitation)
        return invitation


async def get_business_or_404(
    business_uid: uuid.UUID, session: AsyncSession
) -> Business:
    business = await BusinessService().get_business(business_uid, session)
    if business is None:
        raise BusinessNotFound()
    return business


async def get_member_or_404(
    business_uid: uuid.UUID, member_uid: uuid.UUID, session: AsyncSession
) -> BusinessMember:
    member = await BusinessService().get_member(business_uid, member_uid, session)
    if member is None:
        raise MemberNotFound()
    return member
