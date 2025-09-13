#!/bin/sh

# Get port from environment variable or default to 8080
PORT=${PORT:-8080}

# Apply database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn Ecommerce.wsgi:application \
    --worker-tmp-dir /dev/shm \
    --bind 0.0.0.0:$PORT \
    --workers 4 \
    --timeout 120