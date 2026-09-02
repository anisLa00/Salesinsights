"""Sales Insight FastAPI application factory / entrypoint.

Run with:  uvicorn src:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.auth.router import auth_router
from src.customers.routes import customer_router
from src.db.main import init_db
from src.insights.routes import insight_router
from src.products.routes import product_router
from src.sales.routes import sale_router

from .errors import register_all_errors
from .middleware import register_middleware


@asynccontextmanager
async def life_span(app: FastAPI):
    print("Server is starting ...")
    await init_db()
    yield
    print("Server has stopped.")


version = "v1"
version_prefix = f"/api/{version}"

app = FastAPI(
    title="Sales Insight",
    description="AI-powered sales analytics REST API.",
    version=version,
    docs_url=f"{version_prefix}/docs",
    redoc_url=f"{version_prefix}/redoc",
    openapi_url=f"{version_prefix}/openapi.json",
    license_info={"name": "MIT", "url": "https://opensource.org/license/mit/"},
    lifespan=life_span,
)

register_all_errors(app)
register_middleware(app)

app.include_router(auth_router, prefix=f"{version_prefix}/auth", tags=["auth"])
app.include_router(product_router, prefix=f"{version_prefix}/products", tags=["products"])
app.include_router(
    customer_router, prefix=f"{version_prefix}/customers", tags=["customers"]
)
app.include_router(sale_router, prefix=f"{version_prefix}/sales", tags=["sales"])
app.include_router(insight_router, prefix=f"{version_prefix}/insights", tags=["insights"])


@app.get("/", tags=["health"])
async def root():
    return {"service": "Sales Insight", "version": version, "docs": f"{version_prefix}/docs"}
