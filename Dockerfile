# Multi-stage. Final image ~300MB; the stock-Ubuntu original was ~800MB.
# Optional: this image isn't used on the cloud server (systemd path), but kept
# for parity / one-off local runs.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip wheel && pip wheel . -w /wheels


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    TZ=Europe/London

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi8 \
    shared-mime-info \
 && rm -rf /var/lib/apt/lists/* \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links /wheels spongecake-autoreport && rm -rf /wheels

ENTRYPOINT ["spongecake-report"]
CMD ["--watchlist", "/app/watchlist.yaml", "--output", "/app/reports"]
