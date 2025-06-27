#!/bin/bash

# Function to wait for database
wait_for_db() {
    echo "Waiting for database connection..."
    local max_retries=30
    local retry_count=0
    
    until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -ge $max_retries ]; then
            echo "Database did not become available in time"
            exit 1
        fi
        echo "Database is unavailable - sleeping (attempt $retry_count/$max_retries)"
        sleep 2
    done
    
    echo "Database is ready!"
    
    # Additional test with actual connection
    echo "Testing database connection..."
    for i in {1..10}; do
        if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c '\q' 2>/dev/null; then
            echo "Database connection test successful!"
            break
        fi
        echo "Connection test failed, retrying... ($i/10)"
        sleep 3
    done
}

# Check if we're in Cloud Run (Unix socket) or local development (TCP)
if [ -n "$CLOUD_SQL_CONNECTION_NAME" ] && [ "$ENVIRONMENT" = "production" ]; then
    echo "Production environment detected. Using Cloud SQL Unix socket connection."
    # In Cloud Run, we don't need to wait for pg_isready as the socket connection is managed by GCP
else
    echo "Development environment detected. Waiting for PostgreSQL TCP connection..."
    wait_for_db
fi

# Run Alembic migrations
echo "Running database migrations..."
cd /app
alembic upgrade head

echo "Migrations completed successfully!"

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} 