#!/bin/bash
set -e

# Migration script for Enclava platform
# Waits for PostgreSQL to be ready, then runs Alembic migrations

echo "=== Enclava Database Migration Script ==="
echo "Starting migration process..."

# Parse database URL to extract connection parameters
# Expected format: postgresql://user:pass@host:port/dbname
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Extract connection parameters from DATABASE_URL
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):[^\/]*\/.*/\1/p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*@[^:]*:\([0-9]*\)\/.*/\1/p')
DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo "Database connection parameters:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT" 
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"

# Function to check if PostgreSQL is ready
check_postgres() {
    PGPASSWORD="$DB_PASS" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1
}

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=1

while ! check_postgres; do
    if [ $ATTEMPT -gt $MAX_ATTEMPTS ]; then
        echo "ERROR: PostgreSQL did not become ready after $MAX_ATTEMPTS attempts"
        echo "Connection details:"
        echo "  Host: $DB_HOST:$DB_PORT"
        echo "  Database: $DB_NAME"
        echo "  User: $DB_USER"
        exit 1
    fi
    
    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS: PostgreSQL not ready, waiting 2 seconds..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

echo "✓ PostgreSQL is ready!"

# Additional connectivity test with actual connection
echo "Testing database connectivity..."
if ! PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
    echo "ERROR: Failed to connect to PostgreSQL database"
    echo "Please check your DATABASE_URL and database configuration"
    exit 1
fi

echo "✓ Database connectivity confirmed!"

# Show current migration status
echo "Checking current migration status..."
alembic current
echo ""

# Show pending migrations
echo "Checking for pending migrations..."
alembic_heads_output=$(alembic heads)
echo "Migration heads found:"
echo "$alembic_heads_output"

if echo "$alembic_heads_output" | grep -q "(head)"; then
    echo "Running migrations to head..."
    alembic upgrade head
    echo "✓ Migrations completed successfully!"
else
    echo "No pending migrations found."
fi

# Show final migration status
echo ""
echo "Final migration status:"
alembic current

# Show created tables for verification
echo ""
echo "Verifying tables created:"
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename NOT LIKE 'LiteLLM_%' ORDER BY tablename;" \
    -t | sed 's/^ */  - /'

echo ""
echo "=== Migration process completed successfully! ==="
echo "Container will now exit..."