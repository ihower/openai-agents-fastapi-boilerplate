# OpenAI Agents SDK + FastAPI Playbook

A FastAPI sample application integrating OpenAI Agents SDK with Braintrust observability.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- API keys from:
  - OpenAI
  - Tavily
  - Braintrust

## Features

- **Multi-Agent Architecture**: Lead agent with reasoning capabilities (GPT-5-mini) and specialized guardrail agent (GPT-4.1-mini)
- **Conversation Management**: SQLite3-based conversation persistence with custom schema and thread management
- **Context Engineering**: Intelligent context optimization with two-level trimming strategy
  - Tool call output trimming when token usage exceeds 150K tokens
  - Turn-based conversation history pruning when exceeding 200K tokens
- **Parallel Task Execution**: Concurrent guardrail checking, metadata extraction, and follow-up questions generation
- **Custom Function Tools**: Integrated Tavily web search with custom context tracking
- **Server-Sent Events (SSE)**: Real-time streaming responses with extended thinking, tool calls, and follow-up questions
- **Braintrust Integration**: Comprehensive observability with tracing, logging, and token usage monitoring
- **External Prompt Management**: Modular prompt templates stored as separate markdown files
- **Token Usage Analytics**: Detailed tracking of input/output/reasoning tokens and prompt cache hit ratios

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
