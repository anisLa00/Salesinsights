"""Verify that protected endpoints require authentication."""

from .conftest import API_PREFIX


def test_products_requires_authentication(client):
    response = client.get(f"{API_PREFIX}/products/")
    # HTTPBearer(auto_error=True) blocks unauthenticated requests.
    assert response.status_code in (401, 403)


def test_sales_requires_authentication(client):
    response = client.get(f"{API_PREFIX}/sales/")
    assert response.status_code in (401, 403)


def test_insights_requires_authentication(client):
    response = client.get(f"{API_PREFIX}/insights/analyze")
    assert response.status_code in (401, 403)
