"""Tenant isolation — the security boundary of the whole application.

Each test sets up two independent businesses and then has a member of
Business A try to reach Business B's data using a *real, valid* identifier
discovered out of band. Every one of those attempts must fail.
"""

import pytest

from .conftest import (
    API_PREFIX,
    auth_headers,
    create_business,
    create_customer,
    create_product,
    make_user,
)


@pytest.fixture
def two_businesses(db_client):
    """Two separate businesses, each with its own owner, product and customer."""
    alice = make_user(db_client, "alice@example.com")
    bob = make_user(db_client, "bob@example.com")

    business_a = create_business(db_client, alice, "Business A")
    business_b = create_business(db_client, bob, "Business B")

    product_a = create_product(db_client, alice, business_a["uid"], "Laptop A", 1000)
    product_b = create_product(db_client, bob, business_b["uid"], "Laptop B", 2000)
    customer_a = create_customer(db_client, alice, business_a["uid"], "CustA")
    customer_b = create_customer(db_client, bob, business_b["uid"], "CustB")

    return {
        "alice": alice,
        "bob": bob,
        "a": business_a,
        "b": business_b,
        "product_a": product_a,
        "product_b": product_b,
        "customer_a": customer_a,
        "customer_b": customer_b,
    }


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def test_cannot_list_another_businesss_products(db_client, two_businesses):
    response = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/products/",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 403


def test_cannot_read_another_businesss_product_by_uid(db_client, two_businesses):
    """Even scoped to her own business, B's product id must not resolve."""
    response = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/products/"
        f"{two_businesses['product_b']['uid']}",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 404


def test_cannot_update_another_businesss_product(db_client, two_businesses):
    response = db_client.patch(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/products/"
        f"{two_businesses['product_b']['uid']}",
        json={"name": "Hijacked"},
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 404

    # And B's product is untouched.
    intact = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/products/"
        f"{two_businesses['product_b']['uid']}",
        headers=auth_headers(two_businesses["bob"]),
    )
    assert intact.json()["name"] == "Laptop B"


def test_cannot_delete_another_businesss_product(db_client, two_businesses):
    response = db_client.delete(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/products/"
        f"{two_businesses['product_b']['uid']}",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 404

    still_there = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/products/"
        f"{two_businesses['product_b']['uid']}",
        headers=auth_headers(two_businesses["bob"]),
    )
    assert still_there.status_code == 200


def test_product_listing_never_leaks_across_tenants(db_client, two_businesses):
    products = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/products/",
        headers=auth_headers(two_businesses["alice"]),
    ).json()

    names = {p["name"] for p in products}
    assert names == {"Laptop A"}


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
def test_cannot_list_another_businesss_customers(db_client, two_businesses):
    response = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/customers/",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 403


def test_cannot_read_or_update_another_businesss_customer(db_client, two_businesses):
    read = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/customers/"
        f"{two_businesses['customer_b']['uid']}",
        headers=auth_headers(two_businesses["alice"]),
    )
    update = db_client.patch(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/customers/"
        f"{two_businesses['customer_b']['uid']}",
        json={"name": "Hijacked"},
        headers=auth_headers(two_businesses["alice"]),
    )
    assert read.status_code == 404
    assert update.status_code == 404


# ---------------------------------------------------------------------------
# Sales — cross-tenant references must be rejected
# ---------------------------------------------------------------------------
def test_cannot_create_a_sale_using_another_businesss_product(
    db_client, two_businesses
):
    response = db_client.post(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/sales/",
        json={
            "product_uid": two_businesses["product_b"]["uid"],
            "customer_uid": two_businesses["customer_a"]["uid"],
            "quantity": 1,
        },
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "product_not_found"


def test_cannot_create_a_sale_using_another_businesss_customer(
    db_client, two_businesses
):
    response = db_client.post(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/sales/",
        json={
            "product_uid": two_businesses["product_a"]["uid"],
            "customer_uid": two_businesses["customer_b"]["uid"],
            "quantity": 1,
        },
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "customer_not_found"


def test_cannot_list_or_read_another_businesss_sales(db_client, two_businesses):
    sale = db_client.post(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/sales/",
        json={
            "product_uid": two_businesses["product_b"]["uid"],
            "customer_uid": two_businesses["customer_b"]["uid"],
            "quantity": 3,
        },
        headers=auth_headers(two_businesses["bob"]),
    ).json()

    listing = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/sales/",
        headers=auth_headers(two_businesses["alice"]),
    )
    direct = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/sales/{sale['uid']}",
        headers=auth_headers(two_businesses["alice"]),
    )

    assert listing.status_code == 403
    assert direct.status_code == 404


# ---------------------------------------------------------------------------
# Analytics, dashboard, and members
# ---------------------------------------------------------------------------
def test_cannot_read_another_businesss_insights(db_client, two_businesses):
    metrics = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/insights/metrics",
        headers=auth_headers(two_businesses["alice"]),
    )
    analyze = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/insights/analyze",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert metrics.status_code == 403
    assert analyze.status_code == 403


def test_cannot_read_another_businesss_dashboard(db_client, two_businesses):
    response = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/dashboard",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 403


def test_cannot_list_another_businesss_members(db_client, two_businesses):
    response = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/members",
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 403


def test_cannot_invite_into_another_business(db_client, two_businesses):
    response = db_client.post(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/members/invite",
        json={"email": "mole@example.com", "role": "admin"},
        headers=auth_headers(two_businesses["alice"]),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Analytics must aggregate one tenant only
# ---------------------------------------------------------------------------
def test_metrics_only_count_the_callers_business(db_client, two_businesses):
    # A sells 1 x 1000; B sells 5 x 2000 = 10000.
    db_client.post(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/sales/",
        json={
            "product_uid": two_businesses["product_a"]["uid"],
            "customer_uid": two_businesses["customer_a"]["uid"],
            "quantity": 1,
        },
        headers=auth_headers(two_businesses["alice"]),
    )
    db_client.post(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/sales/",
        json={
            "product_uid": two_businesses["product_b"]["uid"],
            "customer_uid": two_businesses["customer_b"]["uid"],
            "quantity": 5,
        },
        headers=auth_headers(two_businesses["bob"]),
    )

    metrics_a = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['a']['uid']}/insights/metrics",
        headers=auth_headers(two_businesses["alice"]),
    ).json()
    metrics_b = db_client.get(
        f"{API_PREFIX}/businesses/{two_businesses['b']['uid']}/insights/metrics",
        headers=auth_headers(two_businesses["bob"]),
    ).json()

    assert metrics_a["total_revenue"] == 1000.0
    assert metrics_a["total_orders"] == 1
    assert metrics_b["total_revenue"] == 10000.0
    assert metrics_b["total_orders"] == 1

    # No trace of the other tenant's catalog in either report.
    assert {p["name"] for p in metrics_a["top_products"]} == {"Laptop A"}
    assert {p["name"] for p in metrics_b["top_products"]} == {"Laptop B"}


def test_legacy_routes_are_also_tenant_scoped(db_client, two_businesses):
    """The backward-compatible flat routes resolve the caller's own business."""
    products = db_client.get(
        f"{API_PREFIX}/products/", headers=auth_headers(two_businesses["alice"])
    ).json()
    assert {p["name"] for p in products} == {"Laptop A"}
