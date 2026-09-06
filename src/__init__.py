"""Sales Insight FastAPI application factory / entrypoint.

Run with:  uvicorn src:app --reload

Routing layout
--------------
Business-scoped (canonical) — the business comes from the URL and is verified
against the caller's membership:

    /api/v1/businesses/{business_uid}/products
    /api/v1/businesses/{business_uid}/customers
    /api/v1/businesses/{business_uid}/sales
    /api/v1/businesses/{business_uid}/insights
    /api/v1/businesses/{business_uid}/dashboard

Legacy (kept for backward compatibility) — identical handlers, but the
business is resolved to the caller's default one:

    /api/v1/products, /api/v1/customers, /api/v1/sales, /api/v1/insights

Both mounts are built from the same router factories, so there is exactly one
implementation of each endpoint.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.auth.router import auth_router
from src.businesses.dependencies import (
    business_context_from_path,
    default_business_context,
)
from src.businesses.routes import business_router
from src.customers.routes import build_customer_router
from src.db.main import init_db
from src.insights.routes import build_dashboard_router, build_insight_router
from src.products.routes import build_product_router
from src.sales.routes import build_sale_router

from .errors import register_all_errors
from .middleware import register_middleware


@asynccontextmanager
async def life_span(app: FastAPI):
    print("Server is starting ...")
    # Convenience for local development. Schema changes are owned by Alembic:
    # run `alembic upgrade head` (the Docker/Render start commands do).
    await init_db()
    yield
    print("Server has stopped.")


version = "v1"
version_prefix = f"/api/{version}"

app = FastAPI(
    title="Sales Insight",
    description=(
        "Multi-tenant, AI-powered sales analytics REST API. Users belong to "
        "one or more businesses through roles (owner/admin/manager/employee); "
        "all products, customers and sales are isolated per business."
    ),
    version=version,
    docs_url=f"{version_prefix}/docs",
    redoc_url=f"{version_prefix}/redoc",
    openapi_url=f"{version_prefix}/openapi.json",
    license_info={"name": "MIT", "url": "https://opensource.org/license/mit/"},
    lifespan=life_span,
)

register_all_errors(app)
register_middleware(app)

# --- Accounts ---
app.include_router(auth_router, prefix=f"{version_prefix}/auth", tags=["auth"])

# --- Businesses, members, invitations ---
app.include_router(
    business_router, prefix=f"{version_prefix}/businesses", tags=["businesses"]
)

# --- Business-scoped resources (canonical) ---
scoped = f"{version_prefix}/businesses/{{business_uid}}"
app.include_router(
    build_product_router(business_context_from_path),
    prefix=f"{scoped}/products",
    tags=["products"],
)
app.include_router(
    build_customer_router(business_context_from_path),
    prefix=f"{scoped}/customers",
    tags=["customers"],
)
app.include_router(
    build_sale_router(business_context_from_path),
    prefix=f"{scoped}/sales",
    tags=["sales"],
)
app.include_router(
    build_insight_router(business_context_from_path),
    prefix=f"{scoped}/insights",
    tags=["insights"],
)
app.include_router(
    build_dashboard_router(business_context_from_path),
    prefix=f"{scoped}/dashboard",
    tags=["dashboard"],
)

# --- Legacy flat routes: same handlers, default business resolved from the
# caller's memberships. Kept so existing clients keep working. ---
app.include_router(
    build_product_router(default_business_context),
    prefix=f"{version_prefix}/products",
    tags=["products (default business)"],
)
app.include_router(
    build_customer_router(default_business_context),
    prefix=f"{version_prefix}/customers",
    tags=["customers (default business)"],
)
app.include_router(
    build_sale_router(default_business_context),
    prefix=f"{version_prefix}/sales",
    tags=["sales (default business)"],
)
app.include_router(
    build_insight_router(default_business_context),
    prefix=f"{version_prefix}/insights",
    tags=["insights (default business)"],
)


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "Sales Insight",
        "version": version,
        "docs": f"{version_prefix}/docs",
    }
