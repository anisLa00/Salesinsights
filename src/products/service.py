"""Database operations for products.

Every query is scoped by ``business_uid``. Lookups take the business as part
of the WHERE clause rather than filtering after the fetch, so a product id
belonging to another tenant simply does not resolve.
"""

import uuid

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Product

from .schemas import ProductCreateModel, ProductUpdateModel


class ProductService:
    async def get_all_products(
        self, business_uid: uuid.UUID, session: AsyncSession
    ) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.business_uid == business_uid)
            .order_by(desc(Product.created_at))
        )
        result = await session.exec(statement)
        return result.all()

    async def get_product(
        self, business_uid: uuid.UUID, product_uid: uuid.UUID, session: AsyncSession
    ) -> Product | None:
        statement = select(Product).where(
            Product.uid == product_uid,
            Product.business_uid == business_uid,
        )
        result = await session.exec(statement)
        return result.first()

    async def create_product(
        self,
        business_uid: uuid.UUID,
        product_data: ProductCreateModel,
        session: AsyncSession,
    ) -> Product:
        new_product = Product(**product_data.model_dump(), business_uid=business_uid)
        session.add(new_product)
        await session.commit()
        await session.refresh(new_product)
        return new_product

    async def update_product(
        self,
        business_uid: uuid.UUID,
        product_uid: uuid.UUID,
        update_data: ProductUpdateModel,
        session: AsyncSession,
    ) -> Product | None:
        product = await self.get_product(business_uid, product_uid, session)
        if product is None:
            return None
        # exclude_unset: only overwrite fields the caller actually sent.
        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(product, key, value)
        await session.commit()
        await session.refresh(product)
        return product

    async def delete_product(
        self, business_uid: uuid.UUID, product_uid: uuid.UUID, session: AsyncSession
    ) -> bool:
        product = await self.get_product(business_uid, product_uid, session)
        if product is None:
            return False
        await session.delete(product)
        await session.commit()
        return True
