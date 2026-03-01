# Stage 1: Base build stage
FROM python:3.13-slim AS builder

SHELL ["sh", "-exc"]

# Install build dependencies for psycopg
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure uv to install directly into /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

# Synchronize dependencies without the application itself
RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync \
        --frozen \
        --no-dev \
        --no-install-project

# Copy application and install it
COPY . /src
WORKDIR /src
RUN --mount=type=cache,target=/root/.cache \
    uv sync \
        --frozen \
        --no-dev \
        --no-editable

# Stage 2: Production stage
FROM python:3.13-slim

SHELL ["sh", "-exc"]

# Add the application virtualenv to PATH
ENV PATH=/app/bin:$PATH

# Create non-root user
RUN <<EOT
groupadd -r appuser
useradd -r -d /app -g appuser -N appuser
EOT

# Install runtime dependencies (GDAL packages pull correct dependencies)
RUN <<EOT
apt-get update -qy
apt-get install -qyy \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    netcat-openbsd \
    libpq5 \
    gdal-bin \
    libgeos-c1t64

apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOT

# Create version-agnostic symlinks so GDAL_LIBRARY_PATH=/usr/lib/libgdal.so works
RUN GDAL_LIB="$(find /usr/lib -name 'libgdal.so.*' | sort | tail -1)"; \
    if [ -z "$GDAL_LIB" ]; then echo "Error: libgdal.so.* not found under /usr/lib"; exit 1; fi; \
    ln -sf "$GDAL_LIB" /usr/lib/libgdal.so; \
    GEOS_LIB="$(find /usr/lib -name 'libgeos_c.so.*' | sort | tail -1)"; \
    if [ -z "$GEOS_LIB" ]; then echo "Error: libgeos_c.so.* not found under /usr/lib"; exit 1; fi; \
    ln -sf "$GEOS_LIB" /usr/lib/libgeos_c.so

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy the pre-built /app directory from build stage
COPY --from=builder --chown=appuser:appuser /app /app

# Copy application source code from build stage
COPY --from=builder --chown=appuser:appuser /src/ /app/src/

# Ensure writable directories exist with correct ownership
# (named Docker volumes are initialized from image content, preserving permissions)
RUN mkdir -p /app/src/staticfiles /app/media \
    && chown appuser:appuser /app/src/staticfiles /app/media

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser
WORKDIR /app/src

# Expose the application port
EXPOSE 8000

# Set entrypoint and signal handling
ENTRYPOINT ["/entrypoint.sh"]
STOPSIGNAL SIGINT
