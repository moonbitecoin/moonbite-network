# Direct Python Deployment (No Docker)

## Prerequisites
- VPS (DigitalOcean, Linode, etc.) running Ubuntu 22.04
- SSH access to the VPS
- Domain pointing to VPS IP

## Step 1: SSH into Your VPS
```bash
ssh root@YOUR_VPS_IP
```

## Step 2: Install System Dependencies
```bash
apt update
apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl wget
```

## Step 3: Clone Repository
```bash
cd /opt
git clone https://github.com/moonbitecoin/MoonBite-Coin.git moonbite
cd moonbite
```

## Step 4: Create Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-web.txt gunicorn
```

## Step 5: Create Systemd Service (Auto-Restart)
Create `/etc/systemd/system/moonbite-web.service`:

```ini
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
```

Enable it:
```bash
mkdir -p /var/log/moonbite
chown www-data:www-data /var/log/moonbite
systemctl daemon-reload
systemctl enable moonbite-web
systemctl start moonbite-web
systemctl status moonbite-web
```

## Step 6: Configure Nginx Reverse Proxy
Create `/etc/nginx/sites-available/moonbite`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name moonbite.org www.moonbite.org;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.moonbite.org;

    # SSL Certificates (generated below)
    ssl_certificate /etc/letsencrypt/live/www.moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.moonbite.org/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Proxy to Flask app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
        proxy_request_buffering off;
        client_max_body_size 256k;
    }

    # Static files (serve directly, no proxy)
    location /static/ {
        alias /opt/moonbite/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Logs
    access_log /var/log/nginx/moonbite_access.log;
    error_log /var/log/nginx/moonbite_error.log;
}

# Redirect bare domain to www
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name moonbite.org;

    ssl_certificate /etc/letsencrypt/live/www.moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.moonbite.org/privkey.pem;

    return 301 https://www.moonbite.org$request_uri;
}
```

Enable site:
```bash
ln -s /etc/nginx/sites-available/moonbite /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

## Step 7: Setup SSL Certificate (Let's Encrypt)
```bash
certbot certonly --nginx -d www.moonbite.org -d moonbite.org
systemctl restart nginx
```

Auto-renew (already scheduled by certbot):
```bash
systemctl enable certbot.timer
systemctl start certbot.timer
```

## Step 8: Verify Deployment
```bash
# Check Flask app is running
systemctl status moonbite-web

# Check logs
tail -f /var/log/moonbite/error.log

# Test URL
curl -I https://www.moonbite.org/wallet
```

Should see: `<title>MoonBite Wallet</title>` (NOT "Wallet - MoonBite Dashboard")

---

## Deployment Workflow (Git Auto-Deploy)

Create `/opt/moonbite/deploy.sh`:

```bash
#!/bin/bash
cd /opt/moonbite
git pull origin main
source venv/bin/activate
pip install -r requirements-web.txt
systemctl restart moonbite-web
echo "Deployed at $(date)"
```

Make executable:
```bash
chmod +x /opt/moonbite/deploy.sh
```

### Option A: Manual Deploy
```bash
/opt/moonbite/deploy.sh
```

### Option B: Auto-Deploy on Git Push
Create GitHub webhook that calls deployment endpoint (or use cron):

```bash
# Check for updates every 5 minutes
*/5 * * * * cd /opt/moonbite && git fetch origin && if [ $(git rev-parse HEAD) != $(git rev-parse origin/main) ]; then /opt/moonbite/deploy.sh; fi
```

---

## Monitoring & Logs

```bash
# Flask app logs
tail -f /var/log/moonbite/error.log

# Nginx logs
tail -f /var/log/nginx/moonbite_access.log

# Service status
systemctl status moonbite-web

# Restart if needed
systemctl restart moonbite-web
```

---

## Troubleshooting

**502 Bad Gateway?**
- Check Flask app: `systemctl status moonbite-web`
- Check logs: `tail -f /var/log/moonbite/error.log`

**SSL certificate error?**
- Renew: `certbot renew --force-renewal`
- Check: `certbot certificates`

**Updates not showing?**
- Pull latest: `cd /opt/moonbite && git pull origin main`
- Restart: `systemctl restart moonbite-web`
- Clear browser cache or use incognito

---

## Full Setup Command (Copy-Paste)

```bash
#!/bin/bash
set -e

# Update system
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

# Clone repo
mkdir -p /opt
cd /opt
git clone https://github.com/moonbitecoin/MoonBite-Coin.git moonbite
cd moonbite

# Setup Python
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-web.txt gunicorn

# Create systemd service
mkdir -p /var/log/moonbite
chown www-data:www-data /var/log/moonbite

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

# Setup Nginx
cat > /etc/nginx/sites-available/moonbite << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name moonbite.org www.moonbite.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.moonbite.org;
    ssl_certificate /etc/letsencrypt/live/www.moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.moonbite.org/privkey.pem;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
    location /static/ {
        alias /opt/moonbite/static/;
        expires 30d;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name moonbite.org;
    ssl_certificate /etc/letsencrypt/live/www.moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.moonbite.org/privkey.pem;
    return 301 https://www.moonbite.org$request_uri;
}
EOF

ln -sf /etc/nginx/sites-available/moonbite /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# Setup SSL
certbot certonly --nginx -d www.moonbite.org -d moonbite.org

echo "✓ Deployment complete!"
echo "Visit: https://www.moonbite.org/wallet"
```

Save as `setup.sh` on your local machine, then:
```bash
chmod +x setup.sh
scp setup.sh root@YOUR_VPS_IP:/root/
ssh root@YOUR_VPS_IP
bash /root/setup.sh
```

---

## Advantages Over Docker

✅ **No caching issues** — code changes deploy immediately
✅ **Direct control** — see logs in real-time
✅ **Faster startup** — no image building
✅ **Smaller footprint** — no Docker overhead
✅ **Easy debugging** — SSH directly into running process
✅ **Simple updates** — just git pull + restart
