# MoonBite Dashboard — Flask web app for blockchain interaction
# Runs web_app.py with gunicorn to expose GET /api/blockchain/info and dashboard UI
FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies for web app
RUN pip install --no-cache-dir -r requirements-web.txt

# Expose port 5000 (Railway default PORT env var)
EXPOSE 5000

# Run with gunicorn (production-ready WSGI server)
# Railway sets PORT env var; default to 5000
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 web_app:app"]
