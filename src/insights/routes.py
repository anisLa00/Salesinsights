"""Insight routes: raw metrics, the AI analysis, and the business dashboard.

Analytics are restricted to manager and above; the AI only ever receives
metrics aggregated from the single business in the verified context.
"""

from typing import Callable

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.businesses.dependencies import (
    VIEW_ANALYTICS,
    BusinessContext,
    business_context_from_path,
    require_business_role,
)
from src.db.main import get_session

from .ai import generate_insights
from .schemas import DashboardModel, InsightReport, SalesMetrics
from .service import InsightService

insight_service = InsightService()


def build_insight_router(
    context_dependency: Callable = business_context_from_path,
) -> APIRouter:
    router = APIRouter()

    analytics_ctx = require_business_role(VIEW_ANALYTICS, context_dependency)

    @router.get("/metrics", response_model=SalesMetrics)
    async def get_metrics(
        ctx: BusinessContext = Depends(analytics_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        """Raw aggregated sales metrics for this business."""
        return await insight_service.compute_metrics(ctx.business_uid, session)

    @router.get("/analyze", response_model=InsightReport)
    async def analyze(
        ctx: BusinessContext = Depends(analytics_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        """Aggregate this business's sales and return an AI analysis.

        Falls back to a built-in heuristic when no Anthropic API key is set.
        """
        metrics = await insight_service.compute_metrics(ctx.business_uid, session)
        return await generate_insights(metrics)

    return router


def build_dashboard_router(
    context_dependency: Callable = business_context_from_path,
) -> APIRouter:
    """The dashboard lives at /businesses/{business_uid}/dashboard."""
    router = APIRouter()

    analytics_ctx = require_business_role(VIEW_ANALYTICS, context_dependency)

    @router.get("", response_model=DashboardModel)
    async def get_dashboard(
        ctx: BusinessContext = Depends(analytics_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        return await insight_service.build_dashboard(ctx.business, session)

    return router
