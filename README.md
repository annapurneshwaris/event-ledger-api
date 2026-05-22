# Event Ledger API

A small service that ingests financial transaction events from multiple upstream
systems and exposes account balances. It is built to tolerate the two messy
realities of real upstream feeds:

- **Out-of-order delivery** — an event with an earlier `eventTimestamp` may arrive
  after one with a later timestamp.
- **At-least-once delivery** — the same event may be delivered more than once.

Both are handled by treating stored events as **immutable** and deriving ordering
and balances at read time, with `eventId` as a natural primary key for idempotency.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the architecture, data model, sequence
diagrams, and the reasoning behind the key decisions.

## AI-assisted SDLC

This repo was built with an AI-augmented workflow using Claude Code, organized
around three role-specialized agents — design, development, and QA — defined under
[`.claude/agents/`](.claude/agents/). A runnable orchestrator
([`agents/orchestrator.py`](agents/orchestrator.py)) drives the same agent
definitions end-to-end against the Anthropic API. See
[`docs/AI_SDLC.md`](docs/AI_SDLC.md) for the full workflow and how each agent maps
to its deliverables.

---

## Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI (automatic OpenAPI/Swagger) |
| Persistence | SQLite via SQLAlchemy (embedded, zero setup) |
| Validation | Pydantic v2 |
| Tests | pytest + pytest-cov |

---

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/events` | Submit an event. `201` if created, `200` if a duplicate `eventId`. |
| `GET` | `/events/{id}` | Retrieve a single event. `404` if unknown. |
| `GET` | `/events?account={accountId}` | List an account's events, ordered by `eventTimestamp`. Supports `page` / `page_size`. |
| `GET` | `/accounts/{accountId}/balance` | Net balance: `sum(CREDIT) - sum(DEBIT)`. |
| `GET` | `/health` | Liveness check. |
| `GET` | `/docs` | Interactive Swagger UI. |

---

## Prerequisites

- Python 3.11 or newer
- (Optional) Docker + Docker Compose

---

## Setup & run (local)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Start the application
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000`. Open `http://localhost:8000/docs` for
the interactive Swagger UI.

### Quick smoke test

```bash
# Create an event
curl -X POST localhost:8000/events -H 'Content-Type: application/json' -d '{
  "eventId":"evt-001","accountId":"acct-123","type":"CREDIT",
  "amount":150.00,"currency":"USD","eventTimestamp":"2026-05-15T14:02:11Z"
}'

# Check the balance
curl localhost:8000/accounts/acct-123/balance
```

---

## Run with Docker

```bash
docker compose up --build
```

The service will be available on `http://localhost:8000` with a health check.

---

## Running the tests

```bash
pytest                                  # run everything
pytest --cov=app --cov-report=term-missing   # with a coverage summary
pytest --cov=app --cov-report=html           # writes htmlcov/index.html
```

The suite covers idempotency, out-of-order arrival, balance accuracy, input
validation, and the concurrency/pagination bonus items. See
[`docs/TEST_COVERAGE.md`](docs/TEST_COVERAGE.md) for the coverage report and the
mapping from requirements to tests.

---

## Configuration

All settings are environment variables prefixed with `LEDGER_`:

| Variable | Default | Purpose |
|---|---|---|
| `LEDGER_DATABASE_URL` | `sqlite:///./ledger.db` | Database connection string |
| `LEDGER_LOG_LEVEL` | `INFO` | Log level |
| `LEDGER_DEFAULT_PAGE_SIZE` | `50` | Default page size for event listing |
| `LEDGER_MAX_PAGE_SIZE` | `200` | Upper bound on page size |

---

## Project layout

```
event-ledger-api/
├── app/
│   ├── config.py          # env-driven settings
│   ├── database.py        # engine, session, ORM models (Event, AuditLog)
│   ├── logging_config.py  # structured JSON logging + correlation ids
│   ├── schemas.py         # Pydantic request/response models + validation
│   ├── service.py         # idempotent ingest, balance, ordering, audit
│   └── main.py            # FastAPI app, routes, middleware, error handlers
├── tests/                 # pytest suite (one file per requirement area)
├── docs/                  # design document + diagrams + coverage report
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```
