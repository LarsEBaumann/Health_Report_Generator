ARG UV_VERSION=0.8.14
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

FROM rocker/r-ver:4.3.2

ARG QUARTO_VERSION=1.3.353

ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RENV_CONFIG_CACHE_ENABLED=false \
    HEALTH_REPORT_R_LIBRARY=/opt/health-report-r-library \
    R_LIBS_USER=/opt/health-report-r-library \
    PATH="/opt/health-report-venv/bin:/opt/tex/.TinyTeX/bin/x86_64-linux:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git xz-utils perl make g++ gfortran \
       pkg-config libuv1-dev \
       libcurl4-openssl-dev libssl-dev libxml2-dev \
       libfontconfig1-dev libfreetype6-dev libpng-dev \
       libjpeg-dev libtiff-dev libharfbuzz-dev libfribidi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uvbin /uv /uvx /usr/local/bin/

RUN uv python install 3.11.6 \
    && uv venv --python 3.11.6 /opt/health-report-venv

COPY scripts/health_pipeline/requirements.lock.txt /opt/build/requirements.lock.txt

RUN uv pip install \
      --python /opt/health-report-venv/bin/python \
      -r /opt/build/requirements.lock.txt \
    && uv pip check --python /opt/health-report-venv/bin/python

RUN curl --fail --show-error --location \
      --retry 5 --retry-all-errors --retry-delay 3 \
      --connect-timeout 30 --max-time 600 \
      "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" \
      -o /tmp/quarto.tar.gz \
    && mkdir -p /opt/quarto \
    && tar -xzf /tmp/quarto.tar.gz -C /opt/quarto --strip-components=1 \
    && ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto \
    && rm /tmp/quarto.tar.gz

WORKDIR /opt/r-build
COPY renv.lock ./renv.lock
COPY workflow/restore_r.R ./workflow/restore_r.R

RUN Rscript workflow/restore_r.R \
    && mv .r-library /opt/health-report-r-library \
    && chmod -R a+rX /opt/health-report-r-library \
    && rm -rf /opt/r-build

COPY scripts/ci/install_tinytex.sh /opt/build/install_tinytex.sh

RUN mkdir -p /opt/tex \
    && HOME=/opt/tex bash /opt/build/install_tinytex.sh 2026.10 \
    && chmod -R a+rX /opt/tex

WORKDIR /app

CMD ["snakemake", "--cores", "2"]
