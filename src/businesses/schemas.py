"""Pydantic schemas for businesses, members, and invitations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models import BusinessRole


class BusinessModel(BaseModel):
    uid: uuid.UUID
    name: str
    owner_uid: uuid.UUID
    created_at: datetime
    updated_at: datetime


class BusinessCreateModel(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BusinessUpdateModel(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class BusinessWithRoleModel(BusinessModel):
    """A business plus the calling user's role in it."""

    role: str


class MemberUserModel(BaseModel):
    """The person behind a membership."""

    uid: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str


class BusinessMemberModel(BaseModel):
    uid: uuid.UUID
    business_uid: uuid.UUID
    user_uid: uuid.UUID
    role: str
    is_active: bool
    joined_at: datetime
    user: MemberUserModel | None = None


class MemberUpdateModel(BaseModel):
    role: BusinessRole | None = None
    is_active: bool | None = None


class InvitationCreateModel(BaseModel):
    email: str = Field(max_length=255)
    role: BusinessRole = BusinessRole.EMPLOYEE


class InvitationModel(BaseModel):
    uid: uuid.UUID
    business_uid: uuid.UUID
    email: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None


class InvitationCreatedModel(BaseModel):
    """Returned after inviting someone.

    `invite_token` is included so the flow is testable from Swagger without a
    real inbox; the same token is also emailed via Celery.
    """

    invitation: InvitationModel
    invite_token: str
    accept_url: str


class InvitationAcceptModel(BaseModel):
    token: str
