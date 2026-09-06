"""Business creation, membership, roles, and invitations."""

from .conftest import (
    API_PREFIX,
    auth_headers,
    create_business,
    invite_and_accept,
    make_user,
)


def test_create_business_makes_creator_the_owner(db_client):
    token = make_user(db_client, "owner@example.com")
    business = create_business(db_client, token, "Anis Electronics")

    assert business["name"] == "Anis Electronics"

    # The creator is automatically an owner-role member.
    members = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/members",
        headers=auth_headers(token),
    ).json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["is_active"] is True
    assert members[0]["user"]["email"] == "owner@example.com"


def test_list_businesses_returns_only_your_own(db_client):
    alice = make_user(db_client, "alice@example.com")
    bob = make_user(db_client, "bob@example.com")
    create_business(db_client, alice, "Alice Co")
    create_business(db_client, bob, "Bob Co")

    alice_businesses = db_client.get(
        f"{API_PREFIX}/businesses/", headers=auth_headers(alice)
    ).json()

    assert [b["name"] for b in alice_businesses] == ["Alice Co"]
    assert alice_businesses[0]["role"] == "owner"


def test_a_user_can_belong_to_several_businesses(db_client):
    alice = make_user(db_client, "alice@example.com")
    bob = make_user(db_client, "bob@example.com")

    own = create_business(db_client, alice, "Alice Co")
    bobs = create_business(db_client, bob, "Bob Co")
    invite_and_accept(
        db_client, bob, bobs["uid"], "alice@example.com", "manager", member_token=alice
    )

    businesses = db_client.get(
        f"{API_PREFIX}/businesses/", headers=auth_headers(alice)
    ).json()
    roles = {b["name"]: b["role"] for b in businesses}

    assert roles == {"Alice Co": "owner", "Bob Co": "manager"}
    assert own["uid"] != bobs["uid"]


def test_non_member_cannot_read_or_update_a_business(db_client):
    owner = make_user(db_client, "owner@example.com")
    outsider = make_user(db_client, "outsider@example.com")
    business = create_business(db_client, owner, "Private Co")

    read = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}", headers=auth_headers(outsider)
    )
    update = db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}",
        json={"name": "Hijacked"},
        headers=auth_headers(outsider),
    )

    assert read.status_code == 403
    assert update.status_code == 403


def test_owner_can_rename_business(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Old Name")

    response = db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}",
        json={"name": "New Name"},
        headers=auth_headers(owner),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_invitation_flow_adds_an_active_member(db_client, emails):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")

    invite_and_accept(db_client, owner, business["uid"], "ahmed@example.com")

    members = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/members",
        headers=auth_headers(owner),
    ).json()
    by_email = {m["user"]["email"]: m for m in members}

    assert by_email["ahmed@example.com"]["role"] == "employee"
    assert by_email["ahmed@example.com"]["is_active"] is True
    # The invitation went out through the existing Celery email task.
    assert any("ahmed@example.com" in recipients for recipients, _, _ in emails.sent)


def test_invitation_cannot_be_redeemed_by_a_different_account(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")

    invite = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/members/invite",
        json={"email": "ahmed@example.com", "role": "employee"},
        headers=auth_headers(owner),
    )
    invite_token = invite.json()["invite_token"]

    # A different, logged-in user tries to redeem someone else's invitation.
    interloper = make_user(db_client, "interloper@example.com")
    response = db_client.post(
        f"{API_PREFIX}/businesses/invitations/accept",
        json={"token": invite_token},
        headers=auth_headers(interloper),
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invitation_invalid"


def test_garbage_invitation_token_is_rejected(db_client):
    user = make_user(db_client, "someone@example.com")
    response = db_client.post(
        f"{API_PREFIX}/businesses/invitations/accept",
        json={"token": "not-a-real-token"},
        headers=auth_headers(user),
    )
    assert response.status_code == 400


def test_employee_cannot_manage_the_team(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")
    employee = invite_and_accept(
        db_client, owner, business["uid"], "ahmed@example.com"
    )

    response = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/members/invite",
        json={"email": "someone@example.com", "role": "employee"},
        headers=auth_headers(employee),
    )

    assert response.status_code == 403


def test_owner_can_change_role_and_deactivate_a_member(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")
    invite_and_accept(db_client, owner, business["uid"], "ahmed@example.com")

    members = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/members",
        headers=auth_headers(owner),
    ).json()
    ahmed = next(m for m in members if m["user"]["email"] == "ahmed@example.com")

    promoted = db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}/members/{ahmed['uid']}",
        json={"role": "manager"},
        headers=auth_headers(owner),
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "manager"

    deactivated = db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}/members/{ahmed['uid']}",
        json={"is_active": False},
        headers=auth_headers(owner),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


def test_deactivated_member_loses_access(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")
    employee = invite_and_accept(
        db_client, owner, business["uid"], "ahmed@example.com"
    )

    members = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/members",
        headers=auth_headers(owner),
    ).json()
    ahmed = next(m for m in members if m["user"]["email"] == "ahmed@example.com")
    db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}/members/{ahmed['uid']}",
        json={"is_active": False},
        headers=auth_headers(owner),
    )

    response = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/products/",
        headers=auth_headers(employee),
    )
    assert response.status_code == 403


def test_owner_membership_is_protected(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")
    admin = invite_and_accept(
        db_client, owner, business["uid"], "admin@example.com", "admin"
    )

    members = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/members",
        headers=auth_headers(owner),
    ).json()
    owner_member = next(m for m in members if m["role"] == "owner")

    demote = db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}/members/{owner_member['uid']}",
        json={"role": "employee"},
        headers=auth_headers(admin),
    )
    remove = db_client.delete(
        f"{API_PREFIX}/businesses/{business['uid']}/members/{owner_member['uid']}",
        headers=auth_headers(admin),
    )

    assert demote.status_code == 403
    assert remove.status_code == 403


def test_nobody_can_be_promoted_to_owner(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")
    invite_and_accept(db_client, owner, business["uid"], "ahmed@example.com")

    members = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/members",
        headers=auth_headers(owner),
    ).json()
    ahmed = next(m for m in members if m["user"]["email"] == "ahmed@example.com")

    response = db_client.patch(
        f"{API_PREFIX}/businesses/{business['uid']}/members/{ahmed['uid']}",
        json={"role": "owner"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 403


def test_user_without_a_business_gets_a_clear_error_on_legacy_routes(db_client):
    token = make_user(db_client, "lonely@example.com")
    response = db_client.get(f"{API_PREFIX}/products/", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json()["error_code"] == "no_business_context"
