#!/bin/bash

# Check if we're in Cloud Run (Unix socket) or local development (TCP)
if [ -n "$CLOUD_SQL_CONNECTION_NAME" ] && [ "$ENVIRONMENT" = "production" ]; then
    echo "Production environment detected. Using Cloud SQL Unix socket connection."
    # In Cloud Run, we don't need to wait for pg_isready as the socket connection is managed by GCP
else
    echo "Development environment detected. Waiting for PostgreSQL TCP connection..."
    # Wait for PostgreSQL to be ready (for local development)
    while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
        echo "PostgreSQL is not ready yet. Waiting..."
        sleep 2
    done
    echo "PostgreSQL is ready!"
fi

# Run Alembic migrations
echo "Running database migrations..."
cd /app
alembic upgrade head

echo "Migrations completed successfully!"

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} 