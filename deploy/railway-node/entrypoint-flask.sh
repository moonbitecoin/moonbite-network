#!/bin/bash
# Entrypoint for Flask web_app.py on Railway
# Ensures proper startup and logging

set -e

cd /app

echo "========================================================"
echo "Starting MoonBite Dashboard (Flask)"
echo "========================================================"
echo ""

# Log Python version
python3 --version

echo ""
echo "Installing any remaining dependencies..."
pip install --no-cache-dir -r requirements-web.txt

echo ""
echo "Starting gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers 1 \
  --worker-class sync \
  --timeout 180 \
  --max-requests 1000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  web_app:app
