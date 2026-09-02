"""Seed the database with a verified demo user and sample sales data.

Run it after starting the database:

    python -m src.seed          # create demo data (skips if already seeded)
    python -m src.seed --reset  # wipe sales/products/customers first, then seed

Then log in with:
    email:    demo@example.com
    password: demo123456

The demo user is created pre-verified with the "admin" role, so you can
call every protected endpoint (including /insights/analyze) right away.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import generate_passwd_hash
from src.db.main import async_engine, init_db
from src.db.models import Customer, Product, Sale, User

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo123456"

PRODUCTS = [
    ("Wireless Mouse", "Accessories", 25.00),
    ("Mechanical Keyboard", "Accessories", 80.00),
    ('27" Monitor', "Displays", 320.00),
    ("USB-C Hub", "Accessories", 45.00),
    ("Laptop Stand", "Office", 60.00),
    ("Noise-Cancelling Headphones", "Audio", 150.00),
]

CUSTOMERS = [
    ("Acme Corp", "acme@example.com", "North America"),
    ("Globex", "globex@example.com", "EMEA"),
    ("Initech", "initech@example.com", "North America"),
    ("Umbrella Ltd", "umbrella@example.com", "APAC"),
    ("Soylent", "soylent@example.com", "EMEA"),
    ("Hooli", "hooli@example.com", "APAC"),
]

NUM_SALES = 80


async def seed(reset: bool = False) -> None:
    await init_db()

    session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        if reset:
            # Delete children (sales) before parents to respect FKs.
            await session.exec(delete(Sale))
            await session.exec(delete(Product))
            await session.exec(delete(Customer))
            await session.commit()
            print("Reset: cleared sales, products, and customers.")

        # --- Demo user (pre-verified) ---
        user = (
            await session.exec(select(User).where(User.email == DEMO_EMAIL))
        ).first()
        if user is None:
            user = User(
                username="demo",
                email=DEMO_EMAIL,
                first_name="Demo",
                last_name="User",
                password_hash=generate_passwd_hash(DEMO_PASSWORD),
                is_verified=True,
                role="admin",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user already exists: {DEMO_EMAIL}")

        # --- Skip sample data if products already exist ---
        if (await session.exec(select(Product))).first() is not None:
            print("Sample data already present — skipping. (Use --reset to rebuild.)")
            return

        # --- Products ---
        products = [
            Product(name=name, category=category, unit_price=price)
            for name, category, price in PRODUCTS
        ]
        session.add_all(products)

        # --- Customers ---
        customers = [
            Customer(name=name, email=email, region=region)
            for name, email, region in CUSTOMERS
        ]
        session.add_all(customers)
        await session.commit()
        for p in products:
            await session.refresh(p)
        for c in customers:
            await session.refresh(c)

        # --- Sales (spread over the last ~6 months for a trend) ---
        random.seed(42)
        sales = []
        for _ in range(NUM_SALES):
            product = random.choice(products)
            customer = random.choice(customers)
            quantity = random.randint(1, 5)
            sales.append(
                Sale(
                    product_uid=product.uid,
                    customer_uid=customer.uid,
                    user_uid=user.uid,
                    quantity=quantity,
                    total_amount=round(float(product.unit_price) * quantity, 2),
                    sold_at=datetime.now() - timedelta(days=random.randint(0, 179)),
                )
            )
        session.add_all(sales)
        await session.commit()

        print(
            f"Seeded {len(products)} products, {len(customers)} customers, "
            f"and {len(sales)} sales."
        )

    await async_engine.dispose()
    print("\nDone! Log in at /api/v1/auth/login with:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")
    print("Then try GET /api/v1/insights/analyze")


if __name__ == "__main__":
    asyncio.run(seed(reset="--reset" in sys.argv))
