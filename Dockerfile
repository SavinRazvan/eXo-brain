# File: Dockerfile
# Path: Dockerfile
# Role: Local evaluation container image for the eXo-brain API (uvicorn factory).
# Used By:
#  - docker compose / CI smoke tests
# Depends On:
#  - requirements.txt
# Notes:
#  - Not a production or enterprise deployment template.
#  - Adapter wheels: PyPI-first; clones SavinRazvan/eXo_adapters at v0.1.2 when PyPI lacks the pin.
#  - Set EXO_ENV and secrets via orchestrator env, not baked into the image.

FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG EXO_ADAPTERS_GIT_REF=v0.1.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY scripts/dev/install_adapter_dependencies.sh ./scripts/dev/install_adapter_dependencies.sh
RUN git clone --depth 1 --branch "${EXO_ADAPTERS_GIT_REF}" \
        https://github.com/SavinRazvan/eXo_adapters.git /tmp/eXo_adapters \
    && chmod +x scripts/dev/install_adapter_dependencies.sh \
    && EXO_ADAPTERS_ROOT=/tmp/eXo_adapters ./scripts/dev/install_adapter_dependencies.sh \
    && rm -rf /tmp/eXo_adapters

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
