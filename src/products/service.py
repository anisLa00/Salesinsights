"""Database operations for products."""

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Product

from .schemas import ProductCreateModel, ProductUpdateModel


class ProductService:
    async def get_all_products(self, session: AsyncSession) -> list[Product]:
        statement = select(Product).order_by(desc(Product.created_at))
        result = await session.exec(statement)
        return result.all()

    async def get_product(
        self, product_uid: str, session: AsyncSession
    ) -> Product | None:
        statement = select(Product).where(Product.uid == product_uid)
        result = await session.exec(statement)
        return result.first()

    async def create_product(
        self, product_data: ProductCreateModel, session: AsyncSession
    ) -> Product:
        new_product = Product(**product_data.model_dump())
        session.add(new_product)
        await session.commit()
        await session.refresh(new_product)
        return new_product

    async def update_product(
        self,
        product_uid: str,
        update_data: ProductUpdateModel,
        session: AsyncSession,
    ) -> Product | None:
        product = await self.get_product(product_uid, session)
        if product is None:
            return None
        # exclude_unset: only overwrite fields the caller actually sent.
        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(product, key, value)
        await session.commit()
        await session.refresh(product)
        return product

    async def delete_product(
        self, product_uid: str, session: AsyncSession
    ) -> bool:
        product = await self.get_product(product_uid, session)
        if product is None:
            return False
        await session.delete(product)
        await session.commit()
        return True
