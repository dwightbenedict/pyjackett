# PyJackett for small hosts such as Render's free tier (512 MB, ~0.1 vCPU).
#
#   docker build -t pyjackett .
#   docker run -p 9117:9117 -v pyjackett-data:/data \
#     -e PYJACKETT_API_KEY=... -e PYJACKETT_ADMIN_USERNAME=... \
#     -e PYJACKETT_ADMIN_PASSWORD=... pyjackett
#
# Set the three variables above on any public host: without them a fresh
# install uses a generated API key and the login admin / admin. See "Small
# hosts" in README.md for every PYJACKETT_* setting.
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

# Never run as root; /data holds the configuration, /cache the parsed
# definitions.
RUN useradd --system --uid 10001 --create-home pyjackett \
    && mkdir /data /cache \
    && chown pyjackett /data /cache
USER pyjackett

# Parse the 585 bundled definitions now: starting then costs ~2 s of CPU
# instead of ~7 s, which matters on a fraction of a CPU. The throwaway data
# folder keeps the generated API key out of the image.
ENV PYJACKETT_DEFINITION_CACHE=/cache/definitions.cache
RUN PYJACKETT_DATA=/tmp/warm python -m pyjackett --warm-cache \
    && rm -rf /tmp/warm

# Defaults for a small host; override with -e. The upstream definition sync
# is off because it downloads and parses everything again after every
# restart; rebuild the image to pick up new definitions.
ENV PYJACKETT_DATA=/data \
    PYJACKETT_SYNC_DEFINITIONS=0 \
    PYJACKETT_MAX_CONCURRENCY=6 \
    PYJACKETT_CACHE_MAX_RELEASES=5000 \
    PYJACKETT_SKIP_FAILING=1 \
    PYJACKETT_RETRIES=1 \
    PORT=9117

VOLUME /data
EXPOSE 9117

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/health', timeout=4)"]

# Shell form of the port so the host's $PORT (Render sets it) is used.
CMD ["sh", "-c", "exec python -m pyjackett --host 0.0.0.0 --port $PORT"]
