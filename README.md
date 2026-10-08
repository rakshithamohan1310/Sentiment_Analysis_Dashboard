# Review Data Pipeline — Phase 1: Data Collection

A domain-agnostic pipeline for collecting reviews from Reddit, YouTube, and synthetic demo data. Phase 1 covers data collection only. NLP, sentiment analysis, aspect extraction, trend detection, and dashboards are out of scope for this phase.

---

## Table of contents

1. [What this phase does (and does not do)](#what-this-phase-does)
2. [Project structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Quick start with Docker Compose](#quick-start-with-docker-compose)
5. [Running without Docker (local dev)](#running-without-docker-local-dev)
6. [Getting Reddit credentials](#getting-reddit-credentials)
7. [Getting YouTube credentials](#getting-youtube-credentials)
8. [Demo mode (no credentials needed)](#demo-mode)
9. [Running the tests](#running-the-tests)
10. [API reference](#api-reference)
11. [Domain configuration (YAML)](#domain-configuration)
12. [Real vs mock — what is what](#real-vs-mock)
13. [Privacy and data handling](#privacy-and-data-handling)
14. [What is next (Phase 2)](#what-is-next)

---

## What this phase does

| Capability | Included |
|---|---|
| Postgres schema (sources, raw_reviews, collection_runs) | ✅ |
| Demo adapter (300 synthetic records) | ✅ |
| Reddit adapter (posts + top-level comments, PRAW) | ✅ |
| YouTube adapter (commentThreads, Data API v3) | ✅ |
| Idempotent collection (no duplicates on re-run) | ✅ |
| Exponential backoff retry on transient errors | ✅ |
| Collection run tracking with stats summary | ✅ |
| FastAPI endpoints (collect, status, raw-reviews, health) | ✅ |
| Domain config via YAML (no domain names in core code) | ✅ |
| Author privacy (salted SHA-256 hash, never raw username) | ✅ |
| NLP / sentiment analysis | ❌ Phase 2 |
| Aspect extraction / trend detection | ❌ Phase 2 |
| Dashboard / visualisation | ❌ Phase 2 |

---

## Project structure

```
Sentiment_Analysis/
├── backend/
│   ├── api/
│   │   ├── dependencies.py     # FastAPI DB session dependency
│   │   ├── domain_config.py    # Load domain YAML → CollectorConfig
│   │   ├── routes.py           # All route handlers
│   │   └── schemas.py          # Request / response Pydantic models
│   ├── collectors/
│   │   ├── base.py             # Abstract ReviewCollector + RawRecord schema
│   │   ├── orchestrator.py     # Runs adapters, persists results, tracks runs
│   │   ├── demo/adapter.py     # Loads synthetic JSON from data/demo/
│   │   ├── reddit/adapter.py   # PRAW-based Reddit collector
│   │   └── youtube/adapter.py  # httpx-based YouTube Data API v3 collector
│   ├── config/settings.py      # Pydantic-settings (all values from env vars)
│   ├── database/engine.py      # Async SQLAlchemy engine + session factory
│   ├── models/
│   │   ├── base.py             # DeclarativeBase
│   │   ├── source.py           # sources table
│   │   ├── raw_review.py       # raw_reviews table
│   │   └── collection_run.py   # collection_runs table
│   └── main.py                 # FastAPI app entry point
├── config/
│   └── domains/
│       └── ev.yaml             # Electric-vehicle domain keyword groups
├── data/
│   └── demo/
│       ├── synthetic_reviews.json      # 300 clearly-labelled synthetic records
│       ├── synthetic_reviews_2.json    # (50 records each across 6 files)
│       ├── ...
│       └── generate_demo_data.py       # Script to regenerate demo data
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/0001_initial_schema.py
├── tests/
│   ├── conftest.py             # SQLite in-memory fixtures, no real Postgres needed
│   ├── test_base_collector.py
│   ├── test_demo_adapter.py
│   ├── test_reddit_adapter.py
│   ├── test_youtube_adapter.py
│   ├── test_orchestrator.py
│   ├── test_settings.py
│   └── test_domain_config.py
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 + |
| Docker + Docker Compose | any recent version |
| (optional) Reddit account | for real Reddit collection |
| (optional) Google Cloud account | for real YouTube collection |

---

## Quick start with Docker Compose

```bash
# 1. Clone / unzip the project
cd Sentiment_Analysis

# 2. Create your .env file from the example
cp .env.example .env
# Edit .env and set AUTHOR_HASH_SALT to a random 32-char string.
# Leave Reddit/YouTube credentials empty to use demo mode only.

# 3. Start Postgres and the API
docker-compose up --build

# 4. Verify the API is running
curl http://localhost:8000/api/health
# Expected: {"status":"ok","database":"ok","version":"1.0.0"}

# 5. Run a demo collection (no credentials needed)
curl -X POST http://localhost:8000/api/collect/demo \
  -H "Content-Type: application/json" \
  -d '{"domain_config": "ev", "max_records": 50}'

# 6. Check what was collected
curl "http://localhost:8000/api/raw-reviews?source=demo&limit=5"
```

The API docs are available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

---

## Running without Docker (local dev)

```bash
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# or: source .venv/bin/activate  (Linux/macOS)

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start a local Postgres instance (Docker is easiest)
docker run -d --name reviews_pg \
  -e POSTGRES_USER=pipeline \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=reviews_db \
  -p 5432:5432 \
  postgres:16-alpine

# 4. Set environment variables (or copy .env.example to .env and edit)
copy .env.example .env   # Windows
# Edit .env with your values

# 5. Run Alembic migrations
alembic upgrade head

# 6. Start the API
uvicorn backend.main:app --reload --port 8000
```

---

## Getting Reddit credentials

1. Log in to Reddit and go to <https://www.reddit.com/prefs/apps>
2. Click **Create another app…**
3. Choose **script** as the application type
4. Fill in any name and redirect URI (e.g. `http://localhost`)
5. Note the **client ID** (shown under the app name) and **client secret**
6. Add to `.env`:

```dotenv
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=ReviewPipeline/0.1 by YourRedditUsername
```

Reddit script-type apps allow read-only access without a user login.
The pipeline uses PRAW's read-only mode and never posts, votes, or modifies anything.

**Rate limits:** Reddit allows 60 requests per minute for OAuth2 script apps. PRAW handles this automatically.

---

## Getting YouTube credentials

1. Go to <https://console.cloud.google.com> and create a project (or use an existing one)
2. Enable the **YouTube Data API v3** in APIs & Services → Library
3. Go to APIs & Services → Credentials → **Create Credentials → API Key**
4. (Recommended) Restrict the key to YouTube Data API v3 only
5. Add to `.env`:

```dotenv
YOUTUBE_API_KEY=your_api_key_here
```

**Quota:** The default daily quota is 10,000 units. A `search.list` costs 100 units; `commentThreads.list` costs 1 unit per page. The pipeline tracks usage in-memory and stops collecting when `remaining units < YOUTUBE_QUOTA_BUFFER` (default: 500). Quota resets daily at midnight Pacific Time.

---

## Demo mode

Demo mode works with zero credentials and is the fastest way to verify the pipeline end-to-end.

```bash
# Collect all 300 synthetic records
curl -X POST http://localhost:8000/api/collect/demo \
  -H "Content-Type: application/json" \
  -d '{"domain_config": "ev", "max_records": 300}'

# Query collected records
curl "http://localhost:8000/api/raw-reviews?source=demo&limit=20"

# Filter by language
curl "http://localhost:8000/api/raw-reviews?source=demo&language=de"
```

Demo data facts:
- 300 records across 6 JSON files in `data/demo/`
- Topics: battery, range, charging, thermal, reliability, ownership
- Languages: English (majority) + German, French, Spanish, Dutch
- All records carry `metadata.synthetic = true`
- Source URLs point to `example-demo.invalid` — they are not real
- Re-running the collection inserts 0 new rows (idempotent)

To regenerate the demo data:
```bash
python data/demo/generate_demo_data.py
```

---

## Running the tests

Tests use an **in-memory SQLite database** — no running Postgres is needed.
All HTTP calls to Reddit and YouTube are mocked with `respx` and `unittest.mock`.

```bash
# Install dependencies first (if not already done)
pip install -r requirements.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_demo_adapter.py -v

# Run a specific test
pytest tests/test_orchestrator.py::test_idempotency_second_run_inserts_nothing -v
```

### Test coverage by file

| Test file | What it covers |
|---|---|
| `test_base_collector.py` | RawRecord validation, datetime coercion, `hash_author_id`, `truncate_text` |
| `test_demo_adapter.py` | Keyword filter, max_records, malformed records, invalid JSON, availability |
| `test_reddit_adapter.py` | Credentials check, posts, comments, author hashing, error isolation |
| `test_youtube_adapter.py` | Credentials check, comments, author hashing, quota exhaustion, comments-disabled |
| `test_orchestrator.py` | Idempotency, partial overlap, adapter isolation, unavailable skip, `collection_runs` tracking, `RunStats` |
| `test_settings.py` | Missing/empty credentials treated as `None`, sync URL conversion |
| `test_domain_config.py` | `ev.yaml` loads, keyword groups, override precedence, no hardcoded "EV" in core code |

---

## API reference

All endpoints are prefixed with `/api`. Interactive docs at `/docs`.

### `POST /api/collect/{source}`

Trigger a collection run for a single source (`demo`, `reddit`, or `youtube`).

**Path parameter:** `source` — the adapter to run.

**Request body:**

```json
{
  "domain_config": "ev",
  "keywords": [],
  "subreddits": [],
  "date_from": null,
  "date_to": null,
  "max_records": 500
}
```

- `domain_config` loads keywords and subreddits from `config/domains/<name>.yaml`.
- `keywords` / `subreddits` override the YAML values if non-empty.
- If the adapter's credentials are missing, returns `503`.

**Response:**

```json
{
  "run_id": 1,
  "source": "demo",
  "status": "completed",
  "records_found": 300,
  "records_inserted": 300,
  "duplicates": 0,
  "rejected": 0,
  "errors": 0,
  "started_at": "2024-01-01T10:00:00Z",
  "completed_at": "2024-01-01T10:00:05Z"
}
```

---

### `GET /api/collection/status`

List recent collection runs.

**Query parameters:** `source`, `limit` (default 20), `offset` (default 0).

---

### `GET /api/raw-reviews`

Query collected raw reviews.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `source` | string | Filter by source (`demo`, `reddit`, `youtube`) |
| `date_from` | datetime | `published_at >=` filter |
| `date_to` | datetime | `published_at <=` filter |
| `ingestion_status` | string | `collected`, `processed`, etc. |
| `language` | string | Language code, e.g. `en`, `de` |
| `limit` | int | Default 50, max 1000 |
| `offset` | int | Default 0 |

Note: `raw_payload` is excluded from the response to avoid large blobs.

---

### `GET /api/health`

Returns `200` if the API is up and the database is reachable.

```json
{"status": "ok", "database": "ok", "version": "1.0.0"}
```

---

## Domain configuration

Domain knowledge lives entirely in `config/domains/<name>.yaml`.
The core pipeline code contains no domain-specific strings.

```yaml
# config/domains/ev.yaml (abbreviated)
keyword_groups:
  battery:
    - "EV battery"
    - "battery degradation"
  charging:
    - "DC fast charging"
    - "charging reliability"
  # ... more groups

subreddits:
  - electricvehicles
  - teslamotors

max_records_per_source: 500
language_filter: null
```

To add a new domain (e.g. smartphones):

```bash
cp config/domains/ev.yaml config/domains/smartphones.yaml
# Edit keywords, subreddits, limits
```

Then collect:

```bash
curl -X POST http://localhost:8000/api/collect/reddit \
  -d '{"domain_config": "smartphones", "max_records": 200}'
```

---

## Real vs mock — what is what

| Component | Real in production | Mocked in tests |
|---|---|---|
| PostgreSQL database | ✅ via docker-compose | In-memory SQLite via `aiosqlite` |
| Reddit API (PRAW) | ✅ when `REDDIT_CLIENT_ID` set | `unittest.mock` (MagicMock + asyncio.to_thread patch) |
| YouTube Data API v3 | ✅ when `YOUTUBE_API_KEY` set | `respx` HTTP mock |
| Demo data | JSON files in `data/demo/` | Same files, no mock needed |
| Author identities | SHA-256 hash only | Same hash function, fixed test salt |
| Source URLs (demo) | Points to `example-demo.invalid` | Not real — clearly labelled |
| Collection run row | Postgres `collection_runs` table | SQLite `collection_runs` table |

**Important:** Demo records have `metadata.synthetic = true` and source URLs on `example-demo.invalid`. They must never be mixed with real data in any downstream analysis without explicit filtering on `source = "demo"`.

---

## Privacy and data handling

- **Author identities** are never stored. Only `SHA-256(AUTHOR_HASH_SALT + original_id)` is kept in `author_id_hash`. The salt is a secret env var. Changing the salt rotates all hashes.
- **No email addresses, phone numbers, tokens, DMs, or private messages** are collected.
- **Reddit:** Only public posts and top-level comments from public subreddits via the official OAuth2 API.
- **YouTube:** Only public comment threads via the official Data API v3. Author channel IDs are hashed, display names are discarded immediately.
- **Demo data:** Entirely synthetic. Author names like `synthetic_user_0042` exist only in the raw JSON and are hashed before DB insert.
- **`raw_payload`:** Stores the full API response for auditability. PII field stripping is the responsibility of Phase 2 enrichment.
- The `data/raw/` directory is git-ignored.

---

## What is next

**Phase 2 (not yet built):**

- Language detection (via `langdetect` or `lingua`)
- NLP preprocessing (cleaning, normalisation)
- Sentiment scoring (per review)
- Aspect extraction (battery / range / charging / thermal / reliability mentions)
- Trend aggregation (by time window, topic, source)
- REST endpoints for aggregated trend data
- Dashboard (charts, tables, filters)

The schema is already designed to support Phase 2: `ingestion_status` on `raw_reviews` will progress from `collected → processing → processed`, and the `metadata` JSONB column will carry aspect and sentiment fields without a schema migration.
