# Multi-stage build for Fly.io deployment
# Stage 1: Builder
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Expose port 8080 for Fly.io
EXPOSE 8080

# Run gunicorn on port 8080 with 3 workers
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8080", "app:app"]
