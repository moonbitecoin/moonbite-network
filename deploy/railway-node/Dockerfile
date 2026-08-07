# MoonBite Dashboard — Flask web app for blockchain interaction
# Runs web_app.py with gunicorn to expose GET /api/blockchain/info and dashboard UI
# REBUILD_TIMESTAMP: 2026-08-07T22:20:00Z - Force fresh bulletproof wallet deployment
FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY . .
COPY deploy/railway-node/entrypoint-flask.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install Python dependencies for web app
RUN pip install --no-cache-dir -r requirements-web.txt

# Expose port 5000 (Railway default PORT env var)
EXPOSE 5000

# Use entrypoint script for better logging and error handling
ENTRYPOINT ["/entrypoint.sh"]
