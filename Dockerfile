# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r fastapi && useradd -r -g fastapi fastapi

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application code and scripts
COPY ./app /app/app
COPY ./scripts/run_migrations.sh /app/run_migrations.sh
COPY ./alembic /app/alembic
COPY ./alembic.ini /app/alembic.ini

# Make script executable and change ownership to non-root user
RUN chmod +x /app/run_migrations.sh && chown -R fastapi:fastapi /app

# Health check (removed for Cloud Run compatibility)
# HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# Expose port (Cloud Run uses PORT environment variable)
EXPOSE 8000

# Run the application with Cloud Run optimized settings
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"] 