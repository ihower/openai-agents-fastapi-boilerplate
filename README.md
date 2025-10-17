# OpenAI Agents SDK + FastAPI Boilerplate

A FastAPI boilerplate integrating OpenAI Agents SDK with Braintrust observability.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- API keys from:
  - OpenAI
  - Tavily
  - Braintrust

## Setup

1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys

3. Install dependencies:
```bash
uv sync
```

4. Run development server:
```bash
uv run uvicorn main:app --reload
```

5. Open http://localhost:8000/static/agent.html

## Production

Run with multiple workers using Gunicorn:

```bash
uv run gunicorn main:app \
  --workers 3 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:7860 \
  --timeout 600
```
