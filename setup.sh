#!/bin/bash
# MoonBite Flask Deployment Setup Script
# Run this on a fresh Ubuntu 22.04 VPS to deploy directly (no Docker)
# Usage: bash setup.sh your-domain.com

set -e

DOMAIN="${1:-www.moonbite.org}"
EMAIL="mbwallets@moonbite.org"

echo "=========================================="
echo "MoonBite Flask Deployment Setup"
echo "Domain: $DOMAIN"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root"
    echo "Run: sudo bash setup.sh $DOMAIN"
    exit 1
fi

# Step 1: Update system
echo "📦 Updating system packages..."
apt update
apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl wget build-essential

# Step 2: Clone repository
echo ""
echo "📥 Cloning MoonBite repository..."
mkdir -p /opt
cd /opt
if [ -d "moonbite" ]; then
    echo "   Repository already exists, updating..."
    cd moonbite
    git pull origin main
    cd ..
else
    git clone https://github.com/moonbitecoin/MoonBite-Coin.git moonbite
fi
cd moonbite

# Step 3: Setup Python virtual environment
echo ""
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-web.txt gunicorn

# Step 4: Create log directory
echo ""
echo "📝 Creating log directory..."
mkdir -p /var/log/moonbite
chown www-data:www-data /var/log/moonbite
chmod 755 /var/log/moonbite

# Step 5: Create systemd service
echo ""
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/moonbite-web.service << 'EOF'
[Unit]
Description=MoonBite Flask Web App
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/moonbite
Environment="PATH=/opt/moonbite/venv/bin"
ExecStart=/opt/moonbite/venv/bin/gunicorn \
    --bind 127.0.0.1:5000 \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --access-logfile /var/log/moonbite/access.log \
    --error-logfile /var/log/moonbite/error.log \
    web_app:app
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable moonbite-web
systemctl start moonbite-web

echo "   ✓ Flask app service created and started"
sleep 2
systemctl status moonbite-web --no-pager | head -5

# Step 6: Configure Nginx
echo ""
echo "🌐 Configuring Nginx..."
cat > /etc/nginx/sites-available/moonbite << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_buffering off;
        proxy_request_buffering off;
        client_max_body_size 256k;
    }

    location /static/ {
        alias /opt/moonbite/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    access_log /var/log/nginx/moonbite_access.log combined;
    error_log /var/log/nginx/moonbite_error.log;
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/moonbite /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
nginx -t

# Step 7: Setup SSL certificate
echo ""
echo "🔒 Setting up SSL certificate with Let's Encrypt..."
echo "   This will prompt you to agree to terms. Press (A)gree when prompted."
certbot certonly --nginx -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email

# Reload Nginx with SSL
systemctl restart nginx

# Step 8: Create deployment script
echo ""
echo "📋 Creating deployment script..."
cat > /opt/moonbite/deploy.sh << 'EOF'
#!/bin/bash
set -e
cd /opt/moonbite
echo "[$(date)] Pulling latest code..."
git pull origin main
source venv/bin/activate
echo "[$(date)] Installing dependencies..."
pip install -r requirements-web.txt > /dev/null 2>&1
echo "[$(date)] Restarting Flask app..."
systemctl restart moonbite-web
echo "[$(date)] ✓ Deployment complete"
EOF
chmod +x /opt/moonbite/deploy.sh

# Step 9: Create auto-update cron job
echo ""
echo "⏱️  Setting up auto-deployment..."
cat > /etc/cron.d/moonbite-deploy << 'EOF'
# Auto-deploy MoonBite on git changes every 5 minutes
*/5 * * * * root cd /opt/moonbite && git fetch origin && if [ $(git rev-parse HEAD) != $(git rev-parse origin/main) ]; then /opt/moonbite/deploy.sh >> /var/log/moonbite/deploy.log 2>&1; fi
EOF

chmod 644 /etc/cron.d/moonbite-deploy

# Step 10: Verify deployment
echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo ""
echo "=========================================="
echo "🌐 Website: https://$DOMAIN"
echo "💳 Wallet: https://$DOMAIN/wallet"
echo "⚙️  Status: systemctl status moonbite-web"
echo "📝 Logs: tail -f /var/log/moonbite/error.log"
echo "🚀 Deploy: /opt/moonbite/deploy.sh"
echo "=========================================="
echo ""
echo "📋 Testing deployment..."
sleep 2

# Test the Flask app is running
if systemctl is-active --quiet moonbite-web; then
    echo "✓ Flask app is running"

    # Test the /wallet endpoint
    if curl -s http://127.0.0.1:5000/wallet | grep -q "MoonBite Wallet"; then
        echo "✓ Wallet endpoint is working (AES-256-GCM bulletproof wallet)"
    else
        echo "⚠ Wallet endpoint returned, but title may be wrong. Check logs:"
        echo "  tail -f /var/log/moonbite/error.log"
    fi
else
    echo "❌ Flask app failed to start. Check:"
    echo "  systemctl status moonbite-web"
    echo "  tail -f /var/log/moonbite/error.log"
    exit 1
fi

echo ""
echo "📚 Full documentation: /opt/moonbite/DEPLOYMENT_DIRECT_PYTHON.md"
echo ""
echo "Next steps:"
echo "1. Test in browser: https://$DOMAIN/wallet"
echo "2. Should show 'MoonBite Wallet' (not 'Wallet - MoonBite Dashboard')"
echo "3. Auto-deploy is enabled - just git push to deploy!"
echo ""
