# Sales Insight 📊

A **multi-tenant, AI-powered sales analytics REST API**. Each business runs its
own team, catalog, customers and sales; the API aggregates that data and turns
it into a plain-language business analysis — powered by **Claude**.

Built with **Python + FastAPI** and **PostgreSQL**, with JWT authentication,
email verification, Redis/Celery background processing, database migrations,
and automated API tests.

> **Multi-tenant by design.** A `User` is a person; a `Business` is a company.
> People join businesses through `BusinessMember`, which carries their role.
> Every product, customer and sale belongs to exactly one business, and every
> query is scoped by `business_uid` — one business can never see another's
> data. This is covered by a dedicated tenant-isolation test suite.

## ✨ Features

- 🏢 **Multiple businesses** on one deployment, fully isolated from each other
- 🧑‍💼 **Teams with roles** — owner / admin / manager / employee
- ✉️ **Employee invitations** by email, using signed, expiring tokens
- 🔐 User authentication and JWT authorization
- 👤 User management with email verification and password reset
- 📦 Product management (per business)
- 🧑‍🤝‍🧑 Customer management (per business)
- 🧾 Sales recording — the employee comes from the JWT and the total is
  computed server-side from the stored unit price
- 🤖 **AI-generated sales insights** (Claude) with a built-in heuristic fallback
- 📈 Metrics: revenue, top products/categories/regions/customers, monthly trend,
  plus **per-employee sales counts and revenue**
- 📊 **Business dashboard** endpoint
- ⚡ Background tasks with Celery
- 🔴 Redis for token blocklist and Celery broker/backend
- 🗄️ PostgreSQL database (async SQLAlchemy + asyncpg)
- 🔄 Database migrations with Alembic
- 🧪 API testing with Pytest, including tenant-isolation tests
- 📖 Interactive API documentation with Swagger/OpenAPI

## 🛠️ Tech Stack

- Python
- FastAPI
- SQLModel + SQLAlchemy (async)
- PostgreSQL (asyncpg)
- Pydantic
- Alembic
- Redis
- Celery
- Pytest
- JWT
- SMTP / Email (fastapi-mail)
- **Anthropic Claude API** (AI insights)
- Swagger / OpenAPI

## 🏗️ Project Structure

```text
sales-insight/
├── migrations/                 # Alembic (async) migrations
│   └── versions/
├── src/
│   ├── auth/                   # signup, login, JWT, email verification
│   ├── businesses/             # businesses, members, invitations
│   │   ├── dependencies.py     # business context + role authorization
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── routes.py
│   ├── products/               # product CRUD (business-scoped)
│   ├── customers/              # customer CRUD (business-scoped)
│   ├── sales/                  # record & browse sales (business-scoped)
│   ├── insights/               # metrics aggregation + AI analysis + dashboard
│   │   ├── service.py          # SQL aggregations
│   │   ├── ai.py               # Claude integration (+ heuristic fallback)
│   │   └── routes.py
│   ├── db/                     # engine/session (main.py), models.py, redis.py
│   ├── celery.py               # background tasks
│   ├── config.py               # settings (pydantic-settings)
│   ├── mail.py                 # email config
│   ├── middleware.py           # CORS, trusted hosts, request logging
│   ├── errors.py               # typed exceptions + handlers
│   └── __init__.py             # FastAPI app
├── .env.example
├── alembic.ini
├── docker-compose.yml          # local PostgreSQL + Redis
├── requirements.txt
├── LICENSE
└── README.md
```

## 🚀 Getting Started

### ⚡ Fastest: one command with Docker

If you have Docker, this runs the whole stack (API + PostgreSQL + Redis) and
seeds demo data automatically:

```bash
git clone https://github.com/anisLa00/Salesinsights.git
cd Salesinsights
docker compose up --build
```

Then open **http://localhost:8000/api/v1/docs** and log in with
`demo@example.com` / `demo123456`.

To enable real Claude analysis, add your key in `docker-compose.yml` (the
commented `ANTHROPIC_API_KEY` line) before starting.

---

### 🐍 Manual setup (step by step)

### 1. Clone and enter the project

```bash
git clone https://github.com/anisLa00/sales-insight.git
cd sales-insight
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:
- `DATABASE_URL` — async PostgreSQL URL (default matches docker-compose)
- `JWT_SECRET` — set a long random string
- `REDIS_URL` — Redis connection (default matches docker-compose)
- `ANTHROPIC_API_KEY` — optional; leave empty to run in **demo mode**
  (insights fall back to a built-in heuristic instead of calling Claude)

### 4. Start PostgreSQL and Redis

```bash
docker compose up -d
```

(Or point `DATABASE_URL` / `REDIS_URL` at your own servers.)

### 5. Create the database schema

Alembic owns the schema. This is safe on both a brand-new database and an
existing one with data (the multi-tenancy migration backfills existing
products/customers/sales into a default business rather than dropping them):

```bash
alembic upgrade head
```

### 6. Load demo data (recommended for a quick try)

```bash
python -m src.seed
```

This creates the business **Anis Electronics Demo** with a pre-verified team
and sample products, customers and sales (attributed to individual employees),
so you can call every endpoint immediately:

```
owner      demo@example.com      / demo123456
employee   employee1@example.com / demo123456
employee   employee2@example.com / demo123456
```

(Run `python -m src.seed --reset` to rebuild this business's sample data. The
reset is scoped to the demo business — other tenants are untouched.)

### 7. Run the API

```bash
uvicorn src:app --reload
```

Open the interactive docs at **http://localhost:8000/api/v1/docs**.

### 8. (Optional) Run the Celery worker for emails

```bash
celery -A src.celery.celery_app worker --loglevel=info
# optional monitoring dashboard:
celery -A src.celery.celery_app flower
```

## 🔑 Full flow (testable from Swagger)

If you ran the seeder, log in as `demo@example.com` / `demo123456` and jump to
step 8. Otherwise the whole lifecycle works end to end:

1. `POST /api/v1/auth/signup` — create an account (verification email queued)
2. `GET  /api/v1/auth/verify/{token}` — verify (link from the email)
3. `POST /api/v1/auth/login` — get an `access_token`, then click **Authorize**
   in Swagger and paste it
4. `POST /api/v1/businesses/` — create your business (you become its owner)
5. `POST /api/v1/businesses/{business_uid}/members/invite` — invite an employee
   by email. The response includes `invite_token` so the flow is testable
   without an inbox; the same token is emailed via Celery.
6. The employee signs up and verifies their own account (steps 1–3)
7. `POST /api/v1/businesses/invitations/accept` — the employee redeems the
   token and becomes an active member
8. `POST /api/v1/businesses/{business_uid}/products/` — add products
9. `POST /api/v1/businesses/{business_uid}/customers/` — add customers
10. `POST /api/v1/businesses/{business_uid}/sales/` — the employee records a
    sale (send only `product_uid`, `customer_uid`, `quantity`)
11. `GET  /api/v1/businesses/{business_uid}/insights/metrics` — the numbers
12. `GET  /api/v1/businesses/{business_uid}/dashboard` — the dashboard
13. `GET  /api/v1/businesses/{business_uid}/insights/analyze` — **AI analysis**

`GET /api/v1/businesses/` lists the businesses you belong to, with your role in
each — that's where you get your `business_uid`.

## 👥 Roles and permissions

Roles live on the membership, so the same person can be an owner in one
business and a manager in another.

| Capability | owner | admin | manager | employee |
|---|:--:|:--:|:--:|:--:|
| Business settings (rename) | ✅ | ✅ | — | — |
| Invite / update / remove members | ✅ | ✅ | — | — |
| Modify the owner's membership | — | — | — | — |
| Create/update/delete products & customers | ✅ | ✅ | ✅ | — |
| Read products & customers | ✅ | ✅ | ✅ | ✅ |
| Record sales | ✅ | ✅ | ✅ | ✅ |
| Delete sales | ✅ | ✅ | ✅ | — |
| Insights, metrics, dashboard | ✅ | ✅ | ✅ | — |

Nobody can be promoted to `owner` through the members API, and the owner's
membership can't be edited or removed — including by an admin.

## 🔒 Tenant isolation

Every product, customer and sale carries a `business_uid`, and every query
filters on it. Lookups are scoped in the `WHERE` clause rather than filtered
after fetching, so another business's UUID simply doesn't resolve:

- Reaching a business you don't belong to → **403** `not_business_member`
- Using another business's product/customer id → **404** (indistinguishable
  from a non-existent record — existence isn't leaked)
- Analytics and the dashboard aggregate a single business only

`business_uid` from a request body is never trusted; it always comes from a
path parameter that has been checked against your active membership.
See `src/tests/test_tenant_isolation.py`.

## ↩️ Backward compatibility

The pre-multi-tenancy flat routes still work:

| Legacy route | Behaviour |
|---|---|
| `/api/v1/products`, `/api/v1/customers`, `/api/v1/sales`, `/api/v1/insights` | Resolve your **default business** (one you own, else your oldest active membership) |

They are the *same handlers* as the business-scoped routes — both mounts are
built from one router factory, so there is a single implementation of each
endpoint. If you belong to no business yet, they return **404**
`no_business_context` telling you to create one.

Two deliberate breaking changes to `POST .../sales`, both security fixes:
`user_uid` and `total_amount` are no longer accepted from the client. The
employee comes from the JWT and the total is computed from the stored unit
price (`unit_price × quantity`).

## 🧠 How the AI insights work

`GET /api/v1/insights/analyze` aggregates your sales into `SalesMetrics`
(revenue, top products/categories/regions/customers, monthly trend) and sends
them to Claude with an analyst system prompt. The model returns a JSON report
(summary, key findings, recommendations). If no `ANTHROPIC_API_KEY` is set, a
deterministic heuristic produces the same shape of report so the endpoint
always works. The response's `source` field is `"ai"` or `"heuristic"`.

### Example `GET /api/v1/insights/analyze` response

```json
{
  "summary": "Across 80 orders the business generated $28,915.00 in revenue (235 units, $361.44 average order value).",
  "key_findings": [
    {"title": "Best-selling product", "detail": "'27\" Monitor' leads with $14,400.00 (50% of total revenue)."},
    {"title": "Leading category", "detail": "'Displays' is the top category at $14,400.00."},
    {"title": "Strongest region", "detail": "'APAC' contributes the most revenue ($15,930.00)."},
    {"title": "Revenue trend", "detail": "Monthly revenue moved up from $4,295.00 (2026-03) to $4,685.00 (2026-08)."}
  ],
  "recommendations": [
    "Revenue is concentrated in '27\" Monitor'. Diversify the catalog to reduce dependence on a single product.",
    "'EMEA' is the weakest region ($6,175.00). Consider targeted campaigns there.",
    "Focus retention on top customers — they drive a large share of revenue."
  ],
  "source": "heuristic",
  "metrics": { "...": "the aggregated numbers the analysis was based on" }
}
```

(This is the seeded-demo output. With `ANTHROPIC_API_KEY` set, `source` is
`"ai"` and the narrative is written by Claude from the same metrics.)

## 🧪 Running tests

```bash
pytest
```

The suite has two layers:

- **Routing/validation tests** run anywhere — no database or Redis needed.
- **Integration tests** (businesses, roles, invitations, sales, dashboard, and
  the tenant-isolation suite) run the real app against a throwaway PostgreSQL
  database named by `TEST_DATABASE_URL`. They create and reset that database
  themselves, so the role needs `CREATEDB`:

  ```sql
  ALTER ROLE sales CREATEDB;
  ```

  If no database is reachable these tests **skip** rather than fail, so
  `pytest` stays green in environments without PostgreSQL.

Redis and Celery are stubbed in tests — no broker or SMTP server required.

## ☁️ Deploy to Render

This repo includes a `render.yaml` **Blueprint** that provisions everything
(web service + PostgreSQL + Redis) in one step:

1. Push this repo to GitHub (already done).
2. Go to the [Render dashboard](https://dashboard.render.com/) →
   **New → Blueprint**.
3. Connect this repository. Render reads `render.yaml` and creates the API,
   a PostgreSQL database, and a Redis instance, wiring the env vars together.
4. Click **Apply** and wait for the first deploy.
5. (Optional) In the web service's **Environment** tab, set
   `ANTHROPIC_API_KEY` to enable real Claude analysis.

On first boot the app seeds the demo data, so the live docs are ready at:

```
https://<your-service>.onrender.com/api/v1/docs
```

Log in with `demo@example.com` / `demo123456` and try
`GET /api/v1/insights/analyze`.

> Note: Render's free tier spins the service down after inactivity, so the
> first request after a pause can take ~30–60s to wake up.

## 📄 License

MIT — see [LICENSE](LICENSE).
