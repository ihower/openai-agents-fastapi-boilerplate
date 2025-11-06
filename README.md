# OpenAI Agents SDK + FastAPI Playbook

A FastAPI sample application integrating OpenAI Agents SDK with Braintrust observability.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- API keys from:
  - OpenAI
  - Tavily
  - Braintrust

## Features

(TBD)

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
uv run fastapi dev
```

6. Open http://localhost:8000

## Production

```bash
uv run fastapi run
```

See https://fastapi.tiangolo.com/deployment/manually/ 

### Using Docker

Set up `.env` first, then run:

```bash
docker compose up
```

Open http://localhost:8000

If you change the app code, you need to rebuild:

```bash
docker compose build
```
