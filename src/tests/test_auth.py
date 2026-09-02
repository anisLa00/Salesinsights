"""Auth-related tests that don't require a live database.

Request-body validation runs before the route handler, so these assert the
contract without touching PostgreSQL.
"""

from .conftest import API_PREFIX


def test_signup_rejects_invalid_body(client):
    # Missing required fields -> FastAPI returns 422 before any DB access.
    response = client.post(f"{API_PREFIX}/auth/signup", json={})
    assert response.status_code == 422


def test_signup_rejects_short_password(client):
    payload = {
        "first_name": "Anis",
        "last_name": "Ellafi",
        "username": "anis",
        "email": "anis@example.com",
        "password": "123",  # min_length is 6
    }
    response = client.post(f"{API_PREFIX}/auth/signup", json=payload)
    assert response.status_code == 422
