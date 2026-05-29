# File: Dockerfile
# Path: Dockerfile
# Role: Local evaluation container image for the eXo-brain API (uvicorn factory).
# Used By:
#  - docker compose / CI smoke tests
# Depends On:
#  - requirements.txt
# Notes:
#  - Not a production or enterprise deployment template.
#  - Adapter wheels install from PyPI only (EXO_ADAPTERS_PYPI_ONLY=1); no in-tree or sibling checkout.
#  - Set EXO_ENV and secrets via orchestrator env, not baked into the image.

FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV EXO_ADAPTERS_PYPI_ONLY=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY scripts/dev/install_adapter_dependencies.sh ./scripts/dev/install_adapter_dependencies.sh
RUN chmod +x scripts/dev/install_adapter_dependencies.sh \
    && ./scripts/dev/install_adapter_dependencies.sh

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
