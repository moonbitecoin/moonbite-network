# MoonBite Dashboard — Flask web app with bulletproof wallet
# Fresh build: 2026-08-07T23:00:00Z - Complete rebuild to bypass cache
# Uses wallet-pwa.html with AES-256-GCM encryption
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies first
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .
COPY deploy/railway-node/entrypoint-flask.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install Python dependencies with explicit verification
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements-web.txt

# Verify wallet-pwa.html exists (bulletproof security wallet)
RUN if [ ! -f "/app/templates/wallet-pwa.html" ]; then \
    echo "ERROR: wallet-pwa.html not found!"; \
    exit 1; \
    fi && \
    echo "✓ wallet-pwa.html found and verified"

# Expose port 5000 (Railway default PORT env var)
EXPOSE 5000

# Health check - verify wallet endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://127.0.0.1:5000/wallet || exit 1

# Use entrypoint script for better logging and error handling
ENTRYPOINT ["/entrypoint.sh"]
