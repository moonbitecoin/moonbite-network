# Partner Site Quick Start (5 Minutes)

## TL;DR Setup

### 1. SSH to Server
```bash
ssh root@67.205.154.64
```

### 2. Copy Files
```bash
mkdir -p /opt/partner-site/templates /opt/partner-site/static
cd /opt/partner-site

# Copy Flask app
cat > app.py << 'ENDAPP'
[PASTE app.py content from partner-site-app.py]
ENDAPP

# Copy requirements
cat > requirements.txt << 'ENDREQ'
Flask>=3.0
gunicorn>=21.2
ENDREQ

# Copy HTML template
cat > templates/index.html << 'ENDHTML'
[PASTE templates/index.html content]
ENDHTML
```

### 3. Setup Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Create Systemd Service
```bash
cat > /etc/systemd/system/partner-site.service << 'ENDSVC'
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
ENDSVC

mkdir -p /var/log/partner-site
chown www-data:www-data /var/log/partner-site
```

### 5. Enable Service
```bash
systemctl daemon-reload
systemctl enable partner-site
systemctl start partner-site
systemctl status partner-site
```

### 6. Create Nginx Config
```bash
cat > /etc/nginx/sites-enabled/partner.conf << 'ENDNGINX'
server {
    listen 80;
    listen [::]:80;
    server_name partner.moonbite.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name partner.moonbite.org;

    ssl_certificate /etc/letsencrypt/live/www.moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.moonbite.org/privkey.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:8051;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    access_log /var/log/nginx/partner_access.log;
    error_log /var/log/nginx/partner_error.log;
}
ENDNGINX

nginx -t
systemctl reload nginx
```

### 7. Add DNS (Namecheap)
- Type: **A**
- Name: **partner**
- Value: **67.205.154.64**
- TTL: **3600**

### 8. Test
```bash
# Wait 5 min for DNS propagation
curl -sk https://partner.moonbite.org/
# Should return HTML
```

---

## Files Needed

1. **app.py** - Flask application
2. **requirements.txt** - Python dependencies
3. **templates/index.html** - Homepage template

All files are in this repository!

---

## What Another Claude Session Needs To Do

1. Read this file: `PARTNER_SITE_QUICK_START.md`
2. Read full setup: `PARTNER_SITE_SETUP.md`
3. Copy code from: `partner-site-app.py`
4. Copy requirements from: `partner-site-requirements.txt`
5. Follow the 8 steps above
6. Test: `curl -sk https://partner.moonbite.org/`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Service won't start | `journalctl -xe` to see error |
| 502 Bad Gateway | Check `systemctl status partner-site` |
| DNS not working | Wait 10 min, check `nslookup partner.moonbite.org 8.8.8.8` |
| SSL error | Verify Nginx config with `nginx -t` |

---

## Files in Repository

```
BigCoinBB/
├── PARTNER_SITE_SETUP.md (full guide)
├── PARTNER_SITE_QUICK_START.md (this file)
├── partner-site-app.py (Flask code)
└── partner-site-requirements.txt (dependencies)
```

**All files needed are ready to copy!** ✅
