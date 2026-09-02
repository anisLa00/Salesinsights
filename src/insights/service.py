"""Compute aggregated sales metrics from the database (async)."""

from collections import defaultdict

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Customer, Product, Sale

from .schemas import SalesMetrics, TopItem

TOP_N = 5


def _f(value) -> float:
    """Coerce a possibly-None / Decimal aggregate to a rounded float."""
    return round(float(value or 0), 2)


def _top_items(rows) -> list[TopItem]:
    return [
        TopItem(name=name or "Unknown", revenue=_f(revenue), units=int(units or 0))
        for name, revenue, units in rows
    ]


class InsightService:
    async def compute_metrics(self, session: AsyncSession) -> SalesMetrics:
        # --- Headline totals ---
        totals = (
            await session.exec(
                select(
                    func.coalesce(func.sum(Sale.total_amount), 0),
                    func.count(Sale.uid),
                    func.coalesce(func.sum(Sale.quantity), 0),
                )
            )
        ).one()
        total_revenue = _f(totals[0])
        total_orders = int(totals[1] or 0)
        total_units = int(totals[2] or 0)
        average_order_value = _f(total_revenue / total_orders) if total_orders else 0.0

        # --- Top products by revenue ---
        top_products = _top_items(
            (
                await session.exec(
                    select(
                        Product.name,
                        func.sum(Sale.total_amount),
                        func.sum(Sale.quantity),
                    )
                    .join(Sale, Sale.product_uid == Product.uid)
                    .group_by(Product.name)
                    .order_by(func.sum(Sale.total_amount).desc())
                    .limit(TOP_N)
                )
            ).all()
        )

        # --- Top categories by revenue ---
        top_categories = _top_items(
            (
                await session.exec(
                    select(
                        Product.category,
                        func.sum(Sale.total_amount),
                        func.sum(Sale.quantity),
                    )
                    .join(Sale, Sale.product_uid == Product.uid)
                    .group_by(Product.category)
                    .order_by(func.sum(Sale.total_amount).desc())
                    .limit(TOP_N)
                )
            ).all()
        )

        # --- Revenue by region ---
        revenue_by_region = _top_items(
            (
                await session.exec(
                    select(
                        Customer.region,
                        func.sum(Sale.total_amount),
                        func.sum(Sale.quantity),
                    )
                    .join(Sale, Sale.customer_uid == Customer.uid)
                    .group_by(Customer.region)
                    .order_by(func.sum(Sale.total_amount).desc())
                    .limit(TOP_N)
                )
            ).all()
        )

        # --- Top customers by revenue ---
        top_customers = _top_items(
            (
                await session.exec(
                    select(
                        Customer.name,
                        func.sum(Sale.total_amount),
                        func.sum(Sale.quantity),
                    )
                    .join(Sale, Sale.customer_uid == Customer.uid)
                    .group_by(Customer.name)
                    .order_by(func.sum(Sale.total_amount).desc())
                    .limit(TOP_N)
                )
            ).all()
        )

        # --- Revenue by month (bucketed in Python for DB portability) ---
        monthly: dict[str, float] = defaultdict(float)
        rows = (await session.exec(select(Sale.sold_at, Sale.total_amount))).all()
        for sold_at, amount in rows:
            if sold_at is None:
                continue
            monthly[sold_at.strftime("%Y-%m")] += float(amount or 0)
        revenue_by_month = {k: round(v, 2) for k, v in sorted(monthly.items())}

        return SalesMetrics(
            total_revenue=total_revenue,
            total_orders=total_orders,
            total_units=total_units,
            average_order_value=average_order_value,
            top_products=top_products,
            top_categories=top_categories,
            revenue_by_region=revenue_by_region,
            top_customers=top_customers,
            revenue_by_month=revenue_by_month,
        )
