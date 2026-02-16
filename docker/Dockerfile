FROM ghcr.io/astral-sh/uv:python3.11-bookworm

WORKDIR /app

# Install project dependencies from lockfile (including dev for in-container tests)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --all-groups --no-install-project

# Install the local src-layout package into the virtual environment
COPY src ./src
RUN uv pip install -e .

ENV PATH="/app/.venv/bin:${PATH}"

# Default command can be overridden by docker-compose
CMD ["uv", "run", "uvicorn", "caseflow.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
