# ─────────────────────────────────────────────────────────────────────
# OptionsIQ — Cloud Run Dockerfile
# Python 3.11 slim base. Installs system deps for git (needed for
# the pypmclient install from GitHub) and runs Streamlit on the
# port Cloud Run sets via the $PORT env var (default 8080).
# ─────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Avoid prompts and write .pyc-less, line-buffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: git is required to pip install pypmclient from GitHub.
# build-essential helps wheels that need compilation (numpy/pandas usually
# ship wheels for slim, but keep build tools available as a safety net).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cached)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the app
COPY . .

# Cloud Run injects $PORT (defaults to 8080). Streamlit needs to bind
# to 0.0.0.0 (not localhost) and disable usage stats / file watcher
# noise. CORS/XSRF are turned off because Cloud Run terminates TLS
# upstream and Streamlit's defaults misfire behind that proxy.
ENV PORT=8080 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8080

# Use sh -c so $PORT expands at container start time
CMD streamlit run app.py \
        --server.port=$PORT \
        --server.address=0.0.0.0 \
        --server.headless=true \
        --browser.gatherUsageStats=false
