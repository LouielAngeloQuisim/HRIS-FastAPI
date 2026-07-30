#!/bin/bash
set -e

echo "Starting HRIS Backend..."

# Wait for database
python app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Create initial data
python app/initial_data.py

# Start application
exec fastapi run app/main.py --port 8000 --workers 4