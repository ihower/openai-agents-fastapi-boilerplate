FROM python:3.13-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y  build-essential python3-dev

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Initialize database
RUN uv run python migrate_agent_db.py

# Expose port
EXPOSE 7860

# Run the application
CMD ["uv", "run", "gunicorn", "main:app", "--workers", "3", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:7860", "--timeout", "600"]
