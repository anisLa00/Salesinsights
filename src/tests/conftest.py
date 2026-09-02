"""Shared pytest fixtures.

These tests exercise the app through Starlette's TestClient without any live
PostgreSQL or Redis. The client is NOT used as a context manager, so the
`lifespan` hook (which would call `init_db`) does not run — keeping the suite
fast and dependency-free.
"""

import pytest
from fastapi.testclient import TestClient

from src import app

API_PREFIX = "/api/v1"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
