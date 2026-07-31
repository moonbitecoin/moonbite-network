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

# Run with gunicorn
# Use 1 worker + async to handle memory constraints on Railway
# Increase timeout since Node initialization can be slow
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--worker-class", "sync", \
     "--timeout", "180", \
     "--max-requests", "1000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "web_app:app"]
