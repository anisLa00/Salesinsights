"""Sales recording rules, role permissions, insights, and the dashboard."""

from .conftest import (
    API_PREFIX,
    auth_headers,
    create_business,
    create_customer,
    create_product,
    invite_and_accept,
    make_user,
)


def _setup(db_client):
    owner = make_user(db_client, "owner@example.com")
    business = create_business(db_client, owner, "Anis Electronics")
    product = create_product(db_client, owner, business["uid"], "Laptop", 3000)
    customer = create_customer(db_client, owner, business["uid"], "Acme")
    return owner, business, product, customer


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
def test_total_amount_is_computed_server_side(db_client):
    owner, business, product, customer = _setup(db_client)

    response = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/sales/",
        json={
            "product_uid": product["uid"],
            "customer_uid": customer["uid"],
            "quantity": 2,
        },
        headers=auth_headers(owner),
    )

    assert response.status_code == 201
    # 3000 x 2 — from the stored unit price, not the request.
    assert response.json()["total_amount"] == 6000.0


def test_client_supplied_total_and_user_are_ignored(db_client):
    """Extra fields must not influence the recorded sale."""
    owner, business, product, customer = _setup(db_client)
    attacker = make_user(db_client, "attacker@example.com")

    response = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/sales/",
        json={
            "product_uid": product["uid"],
            "customer_uid": customer["uid"],
            "quantity": 2,
            "total_amount": 1,  # trying to under-report revenue
            "user_uid": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_headers(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["total_amount"] == 6000.0
    assert body["user_uid"] != "00000000-0000-0000-0000-000000000000"
    assert attacker  # the other account was never involved


def test_sale_records_the_employee_from_the_token(db_client):
    owner, business, product, customer = _setup(db_client)
    employee = invite_and_accept(
        db_client, owner, business["uid"], "ahmed@example.com"
    )

    sale = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/sales/",
        json={
            "product_uid": product["uid"],
            "customer_uid": customer["uid"],
            "quantity": 1,
        },
        headers=auth_headers(employee),
    ).json()

    detail = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/sales/{sale['uid']}",
        headers=auth_headers(owner),
    ).json()

    assert detail["user"]["email"] == "ahmed@example.com"
    assert detail["business_uid"] == business["uid"]


def test_employee_can_record_sales_but_not_edit_the_catalog(db_client):
    owner, business, product, customer = _setup(db_client)
    employee = invite_and_accept(
        db_client, owner, business["uid"], "ahmed@example.com"
    )

    recorded = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/sales/",
        json={
            "product_uid": product["uid"],
            "customer_uid": customer["uid"],
            "quantity": 1,
        },
        headers=auth_headers(employee),
    )
    created_product = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/products/",
        json={"name": "Sneaky", "category": "x", "unit_price": 1},
        headers=auth_headers(employee),
    )

    assert recorded.status_code == 201
    assert created_product.status_code == 403


def test_manager_can_manage_catalog_but_not_the_team(db_client):
    owner, business, _, _ = _setup(db_client)
    manager = invite_and_accept(
        db_client, owner, business["uid"], "manager@example.com", "manager"
    )

    created = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/products/",
        json={"name": "Monitor", "category": "Displays", "unit_price": 320},
        headers=auth_headers(manager),
    )
    invited = db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/members/invite",
        json={"email": "x@example.com", "role": "employee"},
        headers=auth_headers(manager),
    )

    assert created.status_code == 201
    assert invited.status_code == 403


# ---------------------------------------------------------------------------
# Insights & dashboard
# ---------------------------------------------------------------------------
def test_employee_cannot_view_analytics(db_client):
    owner, business, _, _ = _setup(db_client)
    employee = invite_and_accept(
        db_client, owner, business["uid"], "ahmed@example.com"
    )

    metrics = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/insights/metrics",
        headers=auth_headers(employee),
    )
    dashboard = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/dashboard",
        headers=auth_headers(employee),
    )

    assert metrics.status_code == 403
    assert dashboard.status_code == 403


def test_dashboard_reports_business_totals_and_employee_breakdown(db_client):
    owner, business, product, customer = _setup(db_client)
    employee = invite_and_accept(
        db_client, owner, business["uid"], "ahmed@example.com"
    )

    # Owner records one sale, employee records two.
    for token, quantity in ((owner, 1), (employee, 2), (employee, 1)):
        db_client.post(
            f"{API_PREFIX}/businesses/{business['uid']}/sales/",
            json={
                "product_uid": product["uid"],
                "customer_uid": customer["uid"],
                "quantity": quantity,
            },
            headers=auth_headers(token),
        )

    dashboard = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/dashboard",
        headers=auth_headers(owner),
    ).json()

    assert dashboard["business"]["name"] == "Anis Electronics"
    assert dashboard["metrics"]["total_sales"] == 3
    assert dashboard["metrics"]["total_revenue"] == 12000.0  # (1+2+1) x 3000
    assert dashboard["metrics"]["products"] == 1
    assert dashboard["metrics"]["customers"] == 1
    assert dashboard["metrics"]["employees"] == 2  # owner + employee

    by_email = {e["email"]: e for e in dashboard["employee_sales"]}
    assert by_email["ahmed@example.com"]["sales_count"] == 2
    assert by_email["ahmed@example.com"]["revenue"] == 9000.0
    assert by_email["owner@example.com"]["sales_count"] == 1


def test_analyze_returns_a_report_without_an_api_key(db_client):
    """With no ANTHROPIC_API_KEY the heuristic fallback still answers."""
    owner, business, product, customer = _setup(db_client)
    db_client.post(
        f"{API_PREFIX}/businesses/{business['uid']}/sales/",
        json={
            "product_uid": product["uid"],
            "customer_uid": customer["uid"],
            "quantity": 2,
        },
        headers=auth_headers(owner),
    )

    report = db_client.get(
        f"{API_PREFIX}/businesses/{business['uid']}/insights/analyze",
        headers=auth_headers(owner),
    ).json()

    assert report["source"] in ("ai", "heuristic")
    assert report["summary"]
    assert report["metrics"]["total_revenue"] == 6000.0
