FROM ghcr.io/astral-sh/uv:python3.11-bookworm

WORKDIR /app

# Install project dependencies from lockfile (including dev for in-container tests)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-groups

ENV PATH="/app/.venv/bin:${PATH}"

# Default command can be overridden by docker-compose
CMD ["uv", "run", "uvicorn", "caseflow.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]