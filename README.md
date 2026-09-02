# Sales Insight 📊

An **AI-powered sales analytics REST API**. Record products, customers, and
sales, then let the API aggregate your data and generate a plain-language
business analysis — powered by **Claude**.

Built with **Python + FastAPI** and **PostgreSQL**, with JWT authentication,
email verification, Redis/Celery background processing, database migrations,
and automated API tests. 

## ✨ Features

- 🔐 User authentication and JWT authorization
- 👤 User management with email verification
- 📦 Product management
- 🧑‍🤝‍🧑 Customer management
- 🧾 Sales recording (auto-computes totals from unit price × quantity)
- 🤖 **AI-generated sales insights** (Claude) with a built-in heuristic fallback
- 📈 Aggregated metrics: revenue, top products/categories/regions/customers, monthly trend
- ⚡ Background tasks with Celery
- 🔴 Redis for token blocklist and Celery broker/backend
- 🗄️ PostgreSQL database (async SQLAlchemy + asyncpg)
- 🔄 Database migrations with Alembic
- 🧪 API testing with Pytest
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
│   ├── products/               # product CRUD
│   ├── customers/              # customer CRUD
│   ├── sales/                  # record & browse sales
│   ├── insights/               # metrics aggregation + AI analysis
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

## 🚀 Getting Started (step by step)

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

The app auto-creates tables on startup, or use Alembic:

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

### 6. Run the API

```bash
uvicorn src:app --reload
```

Open the interactive docs at **http://localhost:8000/api/v1/docs**.

### 7. (Optional) Run the Celery worker for emails

```bash
celery -A src.celery.celery_app worker --loglevel=info
# optional monitoring dashboard:
celery -A src.celery.celery_app flower
```

## 🔑 Typical flow

1. `POST /api/v1/auth/signup` — create an account (a verification email is queued)
2. `GET /api/v1/auth/verify/{token}` — verify (link from the email)
3. `POST /api/v1/auth/login` — get an `access_token`
4. Send `Authorization: Bearer <access_token>` on the calls below:
   - `POST /api/v1/products/` — add products
   - `POST /api/v1/customers/` — add customers
   - `POST /api/v1/sales/` — record sales
   - `GET  /api/v1/insights/metrics` — aggregated numbers
   - `GET  /api/v1/insights/analyze` — **AI analysis** of your sales

## 🧠 How the AI insights work

`GET /api/v1/insights/analyze` aggregates your sales into `SalesMetrics`
(revenue, top products/categories/regions/customers, monthly trend) and sends
them to Claude with an analyst system prompt. The model returns a JSON report
(summary, key findings, recommendations). If no `ANTHROPIC_API_KEY` is set, a
deterministic heuristic produces the same shape of report so the endpoint
always works. The response's `source` field is `"ai"` or `"heuristic"`.

## 🧪 Running tests

```bash
pytest
```

The default suite runs without a live database or Redis (it checks routing,
validation, and auth enforcement).

## 📄 License

MIT — see [LICENSE](LICENSE).
