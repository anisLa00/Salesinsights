"""Insight routes: raw metrics and the AI-generated analysis."""

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import AccessTokenBearer, RoleChecker
from src.db.main import get_session

from .ai import generate_insights
from .schemas import InsightReport, SalesMetrics
from .service import InsightService

insight_router = APIRouter()
insight_service = InsightService()
access_token_bearer = AccessTokenBearer()
role_checker = Depends(RoleChecker(["admin", "user"]))


@insight_router.get("/metrics", response_model=SalesMetrics, dependencies=[role_checker])
async def get_metrics(
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    """Return the raw aggregated sales metrics."""
    return await insight_service.compute_metrics(session)


@insight_router.get(
    "/analyze", response_model=InsightReport, dependencies=[role_checker]
)
async def analyze(
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(access_token_bearer),
):
    """Aggregate the sales data and return an AI-generated business analysis.

    Falls back to a built-in heuristic when no Anthropic API key is set.
    """
    metrics = await insight_service.compute_metrics(session)
    return await generate_insights(metrics)
