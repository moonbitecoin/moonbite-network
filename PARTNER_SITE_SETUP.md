# MoonBite Partner Portal Setup Guide

## Overview
Deploy a partner website on `partner.moonbite.org` using the existing Ubuntu server at `67.205.154.64`.

---

## Step 1: DNS Configuration (Namecheap)

Add new DNS record:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | partner | 67.205.154.64 | 3600 |

**Steps in Namecheap:**
1. Domain List → moonbite.org → Advanced DNS
2. Click "Add Record"
3. Type: A
4. Name: partner
5. Value: 67.205.154.64
6. TTL: 3600
7. Save

**Verify propagation (5-10 min):**
```bash
nslookup partner.moonbite.org 8.8.8.8
# Should return: 67.205.154.64
```

---

## Step 2: Create Partner Site Application

### Option A: Simple Flask App (Recommended)

**File: `/opt/partner-site/app.py`**

```python
from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    """Partner portal homepage"""
    return render_template('index.html')

@app.route('/api/partners')
def get_partners():
    """API endpoint for partner data"""
    partners = [
        {
            'id': 1,
            'name': 'Partner 1',
            'description': 'Description',
            'status': 'active'
        },
        {
            'id': 2,
            'name': 'Partner 2',
            'description': 'Description',
            'status': 'active'
        }
    ]
    return jsonify(partners)

@app.route('/dashboard')
def dashboard():
    """Partner dashboard"""
    return render_template('dashboard.html')

@app.route('/apply', methods=['POST'])
def apply_partner():
    """Apply to become a partner"""
    data = request.get_json()
    # Process application
    return jsonify({'status': 'success', 'message': 'Application received'})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8051, debug=False)
```

**File: `/opt/partner-site/requirements.txt`**

```
Flask>=3.0
gunicorn>=21.2
```

**File: `/opt/partner-site/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MoonBite Partner Portal</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Space Grotesk', sans-serif;
            background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
            color: #e0e0e0;
            min-height: 100vh;
        }

        header {
            background: rgba(15, 20, 25, 0.95);
            padding: 20px 40px;
            border-bottom: 1px solid #00d4ff;
            position: sticky;
            top: 0;
        }

        header h1 {
            color: #00d4ff;
            font-size: 28px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .hero {
            text-align: center;
            margin-bottom: 60px;
        }

        .hero h2 {
            font-size: 48px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #00d4ff, #0099ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            font-size: 18px;
            color: #a0a0a0;
            margin-bottom: 30px;
        }

        .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, #00d4ff, #0099ff);
            color: #0f1419;
            padding: 14px 40px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.3s;
        }

        .cta-button:hover {
            transform: scale(1.05);
        }

        .benefits {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin-top: 60px;
        }

        .benefit-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #00d4ff;
            padding: 30px;
            border-radius: 12px;
            transition: all 0.3s;
        }

        .benefit-card:hover {
            background: rgba(0, 212, 255, 0.1);
            transform: translateY(-5px);
        }

        .benefit-card h3 {
            color: #00d4ff;
            margin-bottom: 15px;
            font-size: 20px;
        }

        .benefit-card p {
            color: #a0a0a0;
            line-height: 1.6;
        }

        footer {
            text-align: center;
            padding: 40px;
            color: #606060;
            border-top: 1px solid #00d4ff;
            margin-top: 80px;
        }
    </style>
</head>
<body>
    <header>
        <h1>🌙 MoonBite Partner Portal</h1>
    </header>

    <div class="container">
        <div class="hero">
            <h2>Become a MoonBite Partner</h2>
            <p>Join our ecosystem of trusted partners and grow with us</p>
            <button class="cta-button" onclick="window.location.href='/apply'">Apply Now</button>
        </div>

        <div class="benefits">
            <div class="benefit-card">
                <h3>💰 Revenue Share</h3>
                <p>Earn competitive commissions on every referral and transaction through our partner program.</p>
            </div>
            <div class="benefit-card">
                <h3>🚀 Growth Tools</h3>
                <p>Access marketing materials, APIs, and tools to help you succeed and scale.</p>
            </div>
            <div class="benefit-card">
                <h3>🤝 Support</h3>
                <p>Dedicated partner support team available 24/7 to help you succeed.</p>
            </div>
            <div class="benefit-card">
                <h3>📊 Analytics</h3>
                <p>Real-time dashboards to track your performance and earnings.</p>
            </div>
            <div class="benefit-card">
                <h3>🔐 Security</h3>
                <p>Enterprise-grade security and compliance for all partner integrations.</p>
            </div>
            <div class="benefit-card">
                <h3>🌍 Global Reach</h3>
                <p>Access to our international network and growing user base.</p>
            </div>
        </div>
    </div>

    <footer>
        <p>&copy; 2026 MoonBite. All rights reserved. | <a href="/" style="color: #00d4ff;">Back to Home</a></p>
    </footer>

    <script>
        console.log('Partner Portal loaded');
    </script>
</body>
</html>
```

---

## Step 3: Nginx Configuration

SSH into server and update Nginx config:

```bash
ssh root@67.205.154.64
```

**Create/Update: `/etc/nginx/sites-enabled/partner.conf`**

```nginx
# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name partner.moonbite.org;
    return 301 https://$server_name$request_uri;
}

# HTTPS server for partner.moonbite.org
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name partner.moonbite.org;

    # SSL certificate (use existing certificate)
    ssl_certificate /etc/letsencrypt/live/www.moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.moonbite.org/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Proxy to Flask app on port 8051
    location / {
        proxy_pass http://127.0.0.1:8051;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Static files
    location /static/ {
        alias /opt/partner-site/static/;
        expires 30d;
    }

    # Logs
    access_log /var/log/nginx/partner_access.log;
    error_log /var/log/nginx/partner_error.log;
}
```

**Test and reload Nginx:**

```bash
nginx -t
systemctl reload nginx
```

---

## Step 4: Deploy Partner Site

SSH into server:

```bash
ssh root@67.205.154.64
```

**Clone/Setup application:**

```bash
# Create directory
mkdir -p /opt/partner-site
cd /opt/partner-site

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p templates static logs
```

**Create systemd service: `/etc/systemd/system/partner-site.service`**

```ini
[Unit]
Description=MoonBite Partner Portal
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/partner-site
Environment="PATH=/opt/partner-site/venv/bin"
ExecStart=/opt/partner-site/venv/bin/gunicorn \
    --bind 127.0.0.1:8051 \
    --workers 2 \
    --timeout 120 \
    --access-logfile /var/log/partner-site/access.log \
    --error-logfile /var/log/partner-site/error.log \
    app:app
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**

```bash
mkdir -p /var/log/partner-site
chown www-data:www-data /var/log/partner-site

systemctl daemon-reload
systemctl enable partner-site
systemctl start partner-site

# Verify
systemctl status partner-site
```

---

## Step 5: Verify Deployment

Test the partner site:

```bash
# Local test
curl -s http://127.0.0.1:8051/ | head -20

# HTTPS test
curl -sk https://partner.moonbite.org/ | head -20
```

---

## Step 6: Auto-Deploy from GitHub (Optional)

Create deploy script: `/opt/partner-site/deploy.sh`

```bash
#!/bin/bash
set -e
cd /opt/partner-site
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
systemctl restart partner-site
echo "Partner site deployed at $(date)"
```

Setup auto-deploy cron:

```bash
*/5 * * * * cd /opt/partner-site && git fetch origin && if [ $(git rev-parse HEAD) != $(git rev-parse origin/main) ]; then bash deploy.sh; fi
```

---

## Monitoring & Logs

```bash
# View logs
tail -f /var/log/partner-site/error.log

# Check service status
systemctl status partner-site

# Restart if needed
systemctl restart partner-site
```

---

## Summary

| Component | Location | Port |
|-----------|----------|------|
| **Wallet** | moonbite.org:8050 | 8050 |
| **Partner** | partner.moonbite.org:8051 | 8051 |
| **Nginx** | Reverse proxy | 80/443 |
| **SSL** | Let's Encrypt (existing) | - |

Both sites run on same Ubuntu server with shared SSL certificate! ✅

---

## Support

If issues arise:
1. Check Nginx config: `nginx -t`
2. Check service: `systemctl status partner-site`
3. Check logs: `tail -f /var/log/partner-site/error.log`
4. Restart: `systemctl restart partner-site`
