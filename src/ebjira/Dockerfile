FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"

# Copy source and tests
COPY src/ src/
COPY tests/ tests/

# Re-install with source
RUN pip install --no-cache-dir ".[dev]"

ENTRYPOINT ["ebjira"]
