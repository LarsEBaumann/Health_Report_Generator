ARG UV_VERSION=0.8.14
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

FROM python:3.11.6-slim

ARG QUARTO_VERSION=1.3.353

ENV UV_PROJECT_ENVIRONMENT=/tmp/health-report-venv \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uvbin /uv /uvx /usr/local/bin/

RUN curl -fsSL \
      "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" \
      -o /tmp/quarto.tar.gz \
    && mkdir -p /opt/quarto \
    && tar -xzf /tmp/quarto.tar.gz -C /opt/quarto --strip-components=1 \
    && ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto \
    && rm /tmp/quarto.tar.gz

WORKDIR /app

CMD ["sh", "-lc", "mkdir -p /tmp/report-home/.config /tmp/report-home/.cache && export HOME=/tmp/report-home XDG_CONFIG_HOME=/tmp/report-home/.config XDG_CACHE_HOME=/tmp/report-home/.cache && uv sync --locked && quarto --version && uv run marimo --version"]
