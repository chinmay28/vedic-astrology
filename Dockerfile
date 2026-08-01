# kundali-web in a container.
#
# Two stages so the runtime image carries no compiler: the builder resolves
# wheels (or compiles pyswisseph where no wheel exists) into a virtualenv at
# /opt/venv, and the runtime stage copies that venv to the SAME path - a
# virtualenv's console scripts hardcode their own path, so it must not move.
#
#   docker build -t kundali-web .
#   docker run -d -p 8777:8777 -v kundali-data:/data --name kundali kundali-web
#
# All state lives in /data (one SQLite file). Nothing is written anywhere else
# except /tmp, which only holds scratch files while a PDF renders.

FROM python:3.12-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml ./
COPY kundali ./kundali
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip wheel \
    && /opt/venv/bin/pip install --no-cache-dir .


FROM python:3.12-slim

# libcairo2 is dlopen()ed by cairosvg for the chart diagrams and PWA icons.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Unprivileged, with a fixed uid so a bind-mounted data directory can be
# chowned to a predictable owner on the host.
RUN useradd --system --uid 10001 --home-dir /data --shell /usr/sbin/nologin \
        kundali \
    && mkdir -p /data \
    && chown kundali:kundali /data

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp \
    KUNDALI_DB=/data/kundali.sqlite

# Declared so a container started without an explicit volume still keeps its
# database out of the (disposable) container layer.
VOLUME ["/data"]

USER kundali
WORKDIR /data
EXPOSE 8777

# No curl in the image; the interpreter is already here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8777/api/health', timeout=4)"]

ENTRYPOINT ["kundali-web"]
CMD ["--host", "0.0.0.0", "--port", "8777", "--db", "/data/kundali.sqlite"]
