"""Seed the database with a demo business, team, and sales data.

Run it after starting the database:

    python -m src.seed          # create demo data (skips if already seeded)
    python -m src.seed --reset  # wipe this business's data first, then seed

Creates the business **Anis Electronics Demo** with:

    owner      demo@example.com      / demo123456
    employee   employee1@example.com / demo123456
    employee   employee2@example.com / demo123456

All accounts are created pre-verified, so you can log in and call every
protected endpoint right away. Sales are attributed to individual employees,
which is what the per-employee dashboard metrics report on.
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import generate_passwd_hash
from src.db.main import async_engine, init_db
from src.db.models import (
    Business,
    BusinessMember,
    BusinessRole,
    Customer,
    Product,
    Sale,
    User,
)

BUSINESS_NAME = "Anis Electronics Demo"
DEMO_PASSWORD = "demo123456"

OWNER = ("demo@example.com", "demo", "Demo", "Owner")
EMPLOYEES = [
    ("employee1@example.com", "employee1", "Ahmed", "Ben Ali"),
    ("employee2@example.com", "employee2", "Sara", "Mansour"),
]

PRODUCTS = [
    ("Laptop", "Computers", 3000.00),
    ("Monitor", "Displays", 320.00),
    ("Mechanical Keyboard", "Accessories", 80.00),
    ("Wireless Mouse", "Accessories", 25.00),
    ("USB-C Hub", "Accessories", 45.00),
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


async def _get_or_create_user(
    session: AsyncSession, email: str, username: str, first: str, last: str
) -> User:
    user = (await session.exec(select(User).where(User.email == email))).first()
    if user is not None:
        return user

    user = User(
        username=username,
        email=email,
        first_name=first,
        last_name=last,
        password_hash=generate_passwd_hash(DEMO_PASSWORD),
        is_verified=True,
        role="user",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    print(f"Created user: {email} / {DEMO_PASSWORD}")
    return user


async def _ensure_member(
    session: AsyncSession, business_uid: uuid.UUID, user: User, role: BusinessRole
) -> None:
    existing = (
        await session.exec(
            select(BusinessMember).where(
                BusinessMember.business_uid == business_uid,
                BusinessMember.user_uid == user.uid,
            )
        )
    ).first()
    if existing is not None:
        return
    session.add(
        BusinessMember(
            business_uid=business_uid,
            user_uid=user.uid,
            role=role.value,
            is_active=True,
        )
    )
    await session.commit()


async def seed(reset: bool = False) -> None:
    await init_db()

    session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        # --- People ---
        owner = await _get_or_create_user(session, *OWNER)
        employees = [
            await _get_or_create_user(session, *employee) for employee in EMPLOYEES
        ]

        # --- Business ---
        business = (
            await session.exec(select(Business).where(Business.name == BUSINESS_NAME))
        ).first()
        if business is None:
            business = Business(name=BUSINESS_NAME, owner_uid=owner.uid)
            session.add(business)
            await session.commit()
            await session.refresh(business)
            print(f"Created business: {BUSINESS_NAME}")
        else:
            print(f"Business already exists: {BUSINESS_NAME}")

        # --- Team ---
        await _ensure_member(session, business.uid, owner, BusinessRole.OWNER)
        for employee in employees:
            await _ensure_member(
                session, business.uid, employee, BusinessRole.EMPLOYEE
            )

        if reset:
            # Scoped to this business only — other tenants are untouched.
            await session.exec(
                delete(Sale).where(Sale.business_uid == business.uid)
            )
            await session.exec(
                delete(Product).where(Product.business_uid == business.uid)
            )
            await session.exec(
                delete(Customer).where(Customer.business_uid == business.uid)
            )
            await session.commit()
            print(f"Reset: cleared data for {BUSINESS_NAME}.")

        already_seeded = (
            await session.exec(
                select(Product).where(Product.business_uid == business.uid)
            )
        ).first()
        if already_seeded is not None:
            print("Sample data already present — skipping. (Use --reset to rebuild.)")
            _print_credentials()
            return

        # --- Catalog ---
        products = [
            Product(
                name=name,
                category=category,
                unit_price=price,
                business_uid=business.uid,
            )
            for name, category, price in PRODUCTS
        ]
        customers = [
            Customer(
                name=name, email=email, region=region, business_uid=business.uid
            )
            for name, email, region in CUSTOMERS
        ]
        session.add_all(products + customers)
        await session.commit()
        for record in products + customers:
            await session.refresh(record)

        # --- Sales, attributed to individual employees ---
        random.seed(42)
        recorders = [owner] + employees
        sales = []
        for _ in range(NUM_SALES):
            product = random.choice(products)
            customer = random.choice(customers)
            recorder = random.choice(recorders)
            quantity = random.randint(1, 5)
            sales.append(
                Sale(
                    business_uid=business.uid,
                    product_uid=product.uid,
                    customer_uid=customer.uid,
                    user_uid=recorder.uid,
                    quantity=quantity,
                    total_amount=round(float(product.unit_price) * quantity, 2),
                    sold_at=datetime.now() - timedelta(days=random.randint(0, 179)),
                )
            )
        session.add_all(sales)
        await session.commit()

        print(
            f"Seeded {len(products)} products, {len(customers)} customers, "
            f"and {len(sales)} sales for {BUSINESS_NAME}."
        )
        print(f"Business uid: {business.uid}")

    await async_engine.dispose()
    _print_credentials()


def _print_credentials() -> None:
    print("\nDone! Log in at /api/v1/auth/login with:")
    print(f"  owner     {OWNER[0]} / {DEMO_PASSWORD}")
    for email, *_ in EMPLOYEES:
        print(f"  employee  {email} / {DEMO_PASSWORD}")
    print("\nThen: GET /api/v1/businesses/ to find your business_uid, and")
    print("      GET /api/v1/businesses/{business_uid}/dashboard")


if __name__ == "__main__":
    asyncio.run(seed(reset="--reset" in sys.argv))
