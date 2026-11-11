# Image of the `rag` service (docker-compose.yml): the Python package with its HTTP API.
# Built by `make up`; the R client's image is separate (src/client/Dockerfile).
FROM python:3.14-slim

# uv, pinned to the version used in development, installs from uv.lock exactly.
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1
WORKDIR /app

# Dependencies first, in their own layer: rebuilt only when pyproject.toml or uv.lock change,
# so a code change rebuilds in seconds.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY README.md ./
COPY src/rag src/rag
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"
USER nobody
EXPOSE 8000
CMD ["rag", "serve", "--host", "0.0.0.0", "--port", "8000"]
