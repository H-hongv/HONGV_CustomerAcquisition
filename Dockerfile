# SDR Agent v3.0 Docker Image
# Multi-stage: lightweight production image
FROM python:3.10-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Data volume
VOLUME ["/app/memory", "/app/exports", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from workflow import checkpointer; checkpointer.get_analytics()" || exit 1

# Default: CLI mode
ENTRYPOINT ["python", "start.py"]
CMD ["--help"]
