"""Database operations for sales.

Sales are the most security-sensitive write in the app: they join a product
and a customer, so both must be proven to belong to the *same* business as the
caller before anything is inserted. The monetary total is always computed here
from the stored unit price — never taken from the request.
"""

import uuid
from decimal import Decimal

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.customers.service import CustomerService
from src.db.models import Sale
from src.errors import CustomerNotFound, ProductNotFound
from src.products.service import ProductService

from .schemas import SaleCreateModel

product_service = ProductService()
customer_service = CustomerService()


class SaleService:
    async def get_all_sales(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> list[Sale]:
        statement = (
            select(Sale)
            .where(Sale.business_uid == business_uid)
            .order_by(desc(Sale.sold_at))
        )
        result = await session.exec(statement)
        return result.all()

    async def get_sale(
        self, business_uid: uuid.UUID, sale_uid: uuid.UUID, session: AsyncSession
    ) -> Sale | None:
        statement = select(Sale).where(
            Sale.uid == sale_uid,
            Sale.business_uid == business_uid,
        )
        result = await session.exec(statement)
        return result.first()

    async def create_sale(
        self,
        business_uid: uuid.UUID,
        user_uid: uuid.UUID,
        sale_data: SaleCreateModel,
        session: AsyncSession,
    ) -> Sale:
        """Record a sale for `business_uid`, entered by `user_uid`.

        Both lookups are business-scoped, so referencing another tenant's
        product or customer is indistinguishable from referencing one that
        does not exist.
        """
        product = await product_service.get_product(
            business_uid, sale_data.product_uid, session
        )
        if product is None:
            raise ProductNotFound()

        customer = await customer_service.get_customer(
            business_uid, sale_data.customer_uid, session
        )
        if customer is None:
            raise CustomerNotFound()

        # Authoritative total: stored unit price x quantity.
        total_amount = Decimal(str(product.unit_price)) * sale_data.quantity

        new_sale = Sale(
            business_uid=business_uid,
            product_uid=product.uid,
            customer_uid=customer.uid,
            user_uid=user_uid,
            quantity=sale_data.quantity,
            total_amount=total_amount,
        )
        if sale_data.sold_at is not None:
            new_sale.sold_at = sale_data.sold_at

        session.add(new_sale)
        await session.commit()
        await session.refresh(new_sale)
        return new_sale

    async def delete_sale(
        self, business_uid: uuid.UUID, sale_uid: uuid.UUID, session: AsyncSession
    ) -> bool:
        sale = await self.get_sale(business_uid, sale_uid, session)
        if sale is None:
            return False
        await session.delete(sale)
        await session.commit()
        return True
