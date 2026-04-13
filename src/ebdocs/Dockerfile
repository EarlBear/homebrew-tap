FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY . /app/
RUN pip install --no-cache-dir ".[dev]"

ENTRYPOINT ["ebdocs"]
