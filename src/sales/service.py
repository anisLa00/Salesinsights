"""Database operations for sales."""

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
    async def get_all_sales(self, session: AsyncSession) -> list[Sale]:
        statement = select(Sale).order_by(desc(Sale.sold_at))
        result = await session.exec(statement)
        return result.all()

    async def get_sale(self, sale_uid: str, session: AsyncSession) -> Sale | None:
        statement = select(Sale).where(Sale.uid == sale_uid)
        result = await session.exec(statement)
        return result.first()

    async def create_sale(
        self, sale_data: SaleCreateModel, user_uid: str, session: AsyncSession
    ) -> Sale:
        product = await product_service.get_product(
            str(sale_data.product_uid), session
        )
        if product is None:
            raise ProductNotFound()

        customer = await customer_service.get_customer(
            str(sale_data.customer_uid), session
        )
        if customer is None:
            raise CustomerNotFound()

        total_amount = sale_data.total_amount
        if total_amount is None:
            total_amount = Decimal(str(product.unit_price)) * sale_data.quantity

        new_sale = Sale(
            product_uid=sale_data.product_uid,
            customer_uid=sale_data.customer_uid,
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

    async def delete_sale(self, sale_uid: str, session: AsyncSession) -> bool:
        sale = await self.get_sale(sale_uid, session)
        if sale is None:
            return False
        await session.delete(sale)
        await session.commit()
        return True
