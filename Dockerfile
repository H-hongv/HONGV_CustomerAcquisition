# SDR Agent v4.0 Docker Image
# Multi-stage: lightweight production image
FROM python:3.10-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends     curl     && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Data volume
VOLUME ["/app/memory", "/app/exports", "/app/logs"]

# Local liveness check: no provider calls and no quota consumption.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import health,sys; sys.exit(0 if health.quick_health_check() else 1)"

# Production default is the 7x24 scheduler. For an ad-hoc CLI run use:
# docker run ... start.py --country Germany --industry automotive
ENTRYPOINT ["python"]
CMD ["daemon.py"]
