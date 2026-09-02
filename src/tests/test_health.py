"""Smoke tests for unauthenticated endpoints."""

from .conftest import API_PREFIX


def test_root_returns_service_info(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Sales Insight"
    assert body["version"] == "v1"


def test_openapi_schema_is_available(client):
    response = client.get(f"{API_PREFIX}/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Sales Insight"
