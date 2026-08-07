#!/bin/bash
set -e

echo "🚀 MoonBite PWA Wallet - Railway Deployment"
echo "=========================================="

# Railway Environment Setup
DOMAIN="${RAILWAY_DOMAIN:-moonbite.org}"
EMAIL="${LETSENCRYPT_EMAIL:-admin@moonbite.org}"
PORT="${PORT:-8000}"
FLASK_PORT="${FLASK_PORT:-5000}"

echo "📍 Domain: $DOMAIN"
echo "📧 Email: $EMAIL"
echo "🔌 Port: $PORT"

# Create directories
mkdir -p /etc/letsencrypt/live/$DOMAIN
mkdir -p /var/log/nginx
mkdir -p /var/cache/nginx

# Check if certificate exists, if not create self-signed for now
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "⚠️  Generating self-signed certificate (replace with Let's Encrypt)..."
    openssl req -x509 -newkey rsa:4096 -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
        -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem -days 365 -nodes \
        -subj "/CN=$DOMAIN/O=MoonBite/C=US"
    echo "✅ Self-signed certificate generated"
else
    echo "✅ Certificate found"
fi

# Update nginx configuration with correct domain
sed -i "s/moonbite.org/$DOMAIN/g" /etc/nginx/nginx.conf
sed -i "s/example.com/$DOMAIN/g" /etc/nginx/nginx.conf

# Start Flask app in background
echo "🐍 Starting Flask application..."
cd /app
python web_app.py &
FLASK_PID=$!
echo "✅ Flask running (PID: $FLASK_PID)"

# Wait for Flask to start
sleep 3
until curl -f http://localhost:$FLASK_PORT > /dev/null 2>&1; do
    echo "⏳ Waiting for Flask to start..."
    sleep 1
done
echo "✅ Flask ready"

# Start nginx
echo "🌐 Starting nginx..."
nginx -g "daemon off;" &
NGINX_PID=$!
echo "✅ Nginx running (PID: $NGINX_PID)"

# Function to renew certificate every 30 days
renew_certificate() {
    while true; do
        sleep 86400  # Check daily
        echo "🔄 Checking certificate expiration..."

        # Try Let's Encrypt renewal (will be manual for now on Railway)
        # In production, use Railway's managed certificates or integrate with Certbot

        if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
            expiration=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" | cut -d= -f2)
            echo "📅 Certificate expires: $expiration"
        fi
    done
}

# Start certificate renewal checker
renew_certificate &
RENEWAL_PID=$!

# Handle signals
trap 'kill $FLASK_PID $NGINX_PID $RENEWAL_PID 2>/dev/null; exit 0' SIGTERM SIGINT

echo ""
echo "✨ MoonBite PWA Wallet is Running!"
echo "=========================================="
echo "🌍 HTTPS: https://$DOMAIN"
echo "📱 Install on iPhone: Share > Add to Home Screen"
echo "🤖 Install on Android: Menu > Install app"
echo ""

# Keep container running
wait
