FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services/api/src:/app/packages/platform/src:/app/packages/adapters/src:/app/packages/data_profiling/src
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY packages ./packages
COPY services/api ./services/api
COPY scripts ./scripts

RUN pip install --no-cache-dir uv==0.11.31 \
    && uv sync --locked --no-dev

USER 65532:65532
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "vda_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
