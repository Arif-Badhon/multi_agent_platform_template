# Stage 1: Build
FROM python:3.11-slim as builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

# Install uv for fast dependency resolution and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && \
    rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml README.md ./
RUN uv pip install --system --no-deps . && \
    uv pip install --system "fastapi" "uvicorn" "websockets" "langgraph" \
    "langchain-community" "ollama" "qdrant-client" "pipecat-ai" \
    "faster-whisper" "pydantic" "pydantic-settings" "loguru" "tenacity" "prometheus-client"

# Stage 2: Runtime
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY src/ ./src/
COPY pyproject.toml README.md ./

# Create a non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Start the FastAPI application with Uvicorn
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
