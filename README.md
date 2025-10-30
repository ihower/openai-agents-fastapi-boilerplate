# OpenAI Agents SDK + FastAPI Boilerplate

A FastAPI boilerplate integrating OpenAI Agents SDK with Braintrust observability.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- API keys from:
  - OpenAI
  - Tavily
  - Braintrust

## Setup

### Local Development

1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys

3. Create data directory:
```bash
mkdir -p data
```

4. Install dependencies:
```bash
uv sync
```

5. Run DB migration:

```bash
uv run python migrate_agent_db.py
```

6. Run development server:
```bash
uv run uvicorn main:app --reload
```

6. Open http://localhost:8000/static/agent.html

## Production

### Using Docker

Set up `.env` first, then run:

```bash
docker compose up
```

If you change the app code, you need to rebuild:

```bash
docker compose build
```

### Local

Run with multiple workers using Gunicorn:

```bash
uv run gunicorn main:app \
  --workers 3 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 600
```
