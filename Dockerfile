# BladeSight: API + built web UI, replay mode. No dataset and no secrets in the image.
FROM node:22-slim AS web
WORKDIR /src
COPY . /src
# web/ may not exist yet (the UI is a separate PR): then the image serves the API only.
RUN if [ -f web/package.json ]; then cd web && npm ci && npm run build; else mkdir -p web/dist; fi

FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev
COPY replay ./replay
COPY docs/evidence ./docs/evidence
COPY --from=web /src/web/dist ./web/dist
# Demo tiles only, streamed from the public archive at build time (never committed, never the
# held-out split); a failure here does not fail the build.
RUN .venv/bin/python -m bladesight.data.demo --replay-dir replay --data-dir data
ENV BLADESIGHT_MODE=replay BLADESIGHT_REPLAY_DIR=/app/replay BLADESIGHT_DATA_DIR=/app/data \
    BLADESIGHT_WEB_DIR=/app/web/dist BLADESIGHT_EVIDENCE_DIR=/app/docs/evidence
EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/uvicorn bladesight.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
