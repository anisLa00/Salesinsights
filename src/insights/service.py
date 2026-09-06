"""Compute aggregated sales metrics for a single business (async).

Every statement here filters on ``Sale.business_uid`` (and joins only rows of
the same business), so analytics can never blend two tenants' data. The month
bucketing is done in Python to stay database-agnostic.
"""

import uuid
from collections import defaultdict

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import (
    Business,
    BusinessMember,
    Customer,
    Product,
    Sale,
    User,
)

from .schemas import (
    DashboardBusiness,
    DashboardMetrics,
    DashboardModel,
    EmployeeStat,
    MonthlyRevenuePoint,
    SalesMetrics,
    TopItem,
)

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
    async def compute_metrics(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> SalesMetrics:
        # --- Headline totals ---
        totals = (
            await session.exec(
                select(
                    func.coalesce(func.sum(Sale.total_amount), 0),
                    func.count(Sale.uid),
                    func.coalesce(func.sum(Sale.quantity), 0),
                ).where(Sale.business_uid == business_uid)
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
                    .where(Sale.business_uid == business_uid)
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
                    .where(Sale.business_uid == business_uid)
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
                    .where(Sale.business_uid == business_uid)
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
                    .where(Sale.business_uid == business_uid)
                    .group_by(Customer.name)
                    .order_by(func.sum(Sale.total_amount).desc())
                    .limit(TOP_N)
                )
            ).all()
        )

        # --- Per-employee operational metrics ---
        sales_by_employee = [
            EmployeeStat(
                user_uid=user_uid,
                name=f"{first or ''} {last or ''}".strip() or (email or "Unknown"),
                email=email,
                sales_count=int(count or 0),
                revenue=_f(revenue),
            )
            for user_uid, first, last, email, revenue, count in (
                await session.exec(
                    select(
                        User.uid,
                        User.first_name,
                        User.last_name,
                        User.email,
                        func.sum(Sale.total_amount),
                        func.count(Sale.uid),
                    )
                    .join(Sale, Sale.user_uid == User.uid)
                    .where(Sale.business_uid == business_uid)
                    .group_by(User.uid, User.first_name, User.last_name, User.email)
                    .order_by(func.sum(Sale.total_amount).desc())
                )
            ).all()
        ]

        # --- Revenue by month (bucketed in Python for DB portability) ---
        monthly: dict[str, float] = defaultdict(float)
        rows = (
            await session.exec(
                select(Sale.sold_at, Sale.total_amount).where(
                    Sale.business_uid == business_uid
                )
            )
        ).all()
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
            sales_by_employee=sales_by_employee,
        )

    async def build_dashboard(
        self, business: Business, session: AsyncSession
    ) -> DashboardModel:
        """Headline counts plus the highlights, for one business."""
        business_uid = business.uid
        metrics = await self.compute_metrics(business_uid, session)

        product_count = (
            await session.exec(
                select(func.count(Product.uid)).where(
                    Product.business_uid == business_uid
                )
            )
        ).one()
        customer_count = (
            await session.exec(
                select(func.count(Customer.uid)).where(
                    Customer.business_uid == business_uid
                )
            )
        ).one()
        employee_count = (
            await session.exec(
                select(func.count(BusinessMember.uid)).where(
                    BusinessMember.business_uid == business_uid,
                    BusinessMember.is_active == True,  # noqa: E712
                )
            )
        ).one()

        return DashboardModel(
            business=DashboardBusiness(uid=business.uid, name=business.name),
            metrics=DashboardMetrics(
                total_revenue=metrics.total_revenue,
                total_sales=metrics.total_orders,
                products=int(product_count or 0),
                customers=int(customer_count or 0),
                employees=int(employee_count or 0),
            ),
            top_products=metrics.top_products,
            top_customers=metrics.top_customers,
            employee_sales=metrics.sales_by_employee,
            monthly_revenue=[
                MonthlyRevenuePoint(month=month, revenue=revenue)
                for month, revenue in metrics.revenue_by_month.items()
            ],
        )
