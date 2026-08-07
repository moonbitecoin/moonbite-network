# MoonBite SSL/TLS Certificate Setup Guide

## Overview

Complete guide for setting up HTTPS with Let's Encrypt certificates for iOS Safari compatibility and PWA deployment.

## Quick Start (5 minutes)

### Docker (Recommended)

```bash
# Clone/navigate to repo
cd /c/Users/usman/Desktop/BigCoinBB

# Build Docker image
docker build -f deploy/Dockerfile.https -t moonbite-https:latest .

# Run with Let's Encrypt (Production)
docker run -d \
  --name moonbite-web \
  -e DOMAIN=moonbite.org \
  -e LETSENCRYPT_EMAIL=admin@moonbite.org \
  -e USE_LETSENCRYPT=true \
  -p 80:80 \
  -p 443:443 \
  -v moonbite-certs:/etc/letsencrypt \
  -v moonbite-logs:/app/logs \
  moonbite-https:latest

# Check status
docker logs -f moonbite-web
```

### Manual Setup (Linux/WSL)

```bash
# 1. Install certbot
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# 2. Get certificate from Let's Encrypt
sudo certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email admin@moonbite.org \
  --domains moonbite.org,www.moonbite.org

# 3. Install nginx
sudo apt-get install -y nginx

# 4. Copy nginx config
sudo cp deploy/nginx.conf /etc/nginx/nginx.conf
sudo cp deploy/ssl.conf /etc/nginx/conf.d/ssl.conf

# 5. Test nginx config
sudo nginx -t

# 6. Start nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# 7. Setup certificate renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

## Certificate Options

### Option 1: Let's Encrypt (Free, Automated)

**Pros**:
- Free
- Automatic renewal
- iOS fully trusts it
- Industry standard

**Cons**:
- 90-day expiration
- Requires automatic renewal

**Setup**:
```bash
certbot certonly --standalone \
  --agree-tos \
  --email admin@moonbite.org \
  --domains moonbite.org,www.moonbite.org
```

**Auto-renewal (Linux/WSL)**:
```bash
# Enable certbot timer
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Manual renewal check
sudo certbot renew --dry-run
```

**Manual renewal (if needed)**:
```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

### Option 2: Self-Signed Certificate (Development Only)

**Pros**:
- No external dependency
- Instant generation
- Works offline

**Cons**:
- Safari shows security warning
- Not suitable for production
- Must be manually updated

**Setup**:
```bash
# Generate private key
openssl genrsa -out /etc/nginx/ssl/private.key 4096

# Generate certificate (365 days)
openssl req -new -x509 \
  -key /etc/nginx/ssl/private.key \
  -out /etc/nginx/ssl/certificate.crt \
  -days 365 \
  -subj "/C=US/ST=California/L=SF/O=MoonBite/CN=localhost"

# Or use the automatic generation in entrypoint script
```

**iPhone Trust (Development)**:
1. Download certificate from browser
2. Settings > General > VPN & Device Management
3. Find certificate
4. Tap "Trust"

### Option 3: Commercial Certificate (High Trust)

**Providers**: Sectigo, GoDaddy, Digicert, GlobalSign

**Process**:
1. Generate CSR (Certificate Signing Request)
2. Submit to provider
3. Verify domain ownership
4. Receive certificate
5. Install on server

```bash
# Generate CSR
openssl req -new \
  -key private.key \
  -out request.csr \
  -subj "/C=US/ST=California/L=SF/O=MoonBite/CN=moonbite.org"

# After receiving certificate from provider
# Install certificate and chain
```

## Certificate Management

### View Certificate Details

```bash
# Check certificate expiration
openssl x509 -in /etc/letsencrypt/live/moonbite.org/fullchain.pem -noout -enddate

# View full certificate info
openssl x509 -in /etc/letsencrypt/live/moonbite.org/fullchain.pem -text -noout

# Check certificate chain
openssl s_client -connect moonbite.org:443 -showcerts

# Verify certificate matches key
openssl x509 -in certificate.crt -noout -modulus | md5sum
openssl rsa -in private.key -noout -modulus | md5sum
# Both should produce same hash
```

### Monitor Certificate Expiration

```bash
# Create renewal reminder script
cat > /opt/check-cert-expiry.sh << 'EOF'
#!/bin/bash
DOMAIN="moonbite.org"
CERT_FILE="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

EXPIRATION=$(openssl x509 -in $CERT_FILE -noout -enddate | cut -d= -f2)
EXPIRATION_EPOCH=$(date -d "$EXPIRATION" +%s)
NOW_EPOCH=$(date +%s)
DAYS_REMAINING=$(( ($EXPIRATION_EPOCH - $NOW_EPOCH) / 86400 ))

echo "Certificate expires in ${DAYS_REMAINING} days"

if [ ${DAYS_REMAINING} -lt 14 ]; then
    echo "WARNING: Certificate expiring soon!"
    # Send email alert
    mail -s "Certificate expiring in ${DAYS_REMAINING} days" admin@moonbite.org
fi
EOF

chmod +x /opt/check-cert-expiry.sh

# Add to crontab (daily check)
(crontab -l 2>/dev/null; echo "0 8 * * * /opt/check-cert-expiry.sh") | crontab -
```

### Renew Certificate Before Expiration

```bash
# Manual renewal (Let's Encrypt)
sudo certbot renew --force-renewal --quiet

# Renewal with email notification
sudo certbot renew --email admin@moonbite.org

# Renewal with specific domains
sudo certbot renew --domains moonbite.org,www.moonbite.org
```

## Nginx Configuration

### Update Nginx Config for SSL

```bash
# Edit nginx configuration
sudo nano /etc/nginx/nginx.conf

# Key settings to verify:
# 1. SSL certificate path correct
# 2. SSL key path correct
# 3. TLS version 1.2+ only
# 4. Strong ciphers configured
# 5. OCSP stapling enabled
```

### Test Nginx Configuration

```bash
# Syntax check
sudo nginx -t

# Dry run (shows what will happen)
sudo nginx -T | grep -A5 "ssl_"

# Reload (no downtime)
sudo systemctl reload nginx

# Check if changes applied
curl -I https://moonbite.org
```

### Verify OCSP Stapling

```bash
# Check OCSP stapling is working
openssl s_client -connect moonbite.org:443 \
  -tlsextdebug 2>&1 | grep -A5 "OCSP response"

# Should see:
# OCSP response:
# OCSP Response Status: successful (0x0)
```

## Firewall & Port Configuration

### Open Required Ports

```bash
# UFW (Ubuntu Firewall)
sudo ufw allow 80/tcp    # HTTP (cert renewal)
sudo ufw allow 443/tcp   # HTTPS (app)
sudo ufw enable

# iptables
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# AWS Security Group
# Allow 80/tcp from 0.0.0.0/0
# Allow 443/tcp from 0.0.0.0/0
```

### Test Port Accessibility

```bash
# Check if ports are open
curl -I http://moonbite.org
curl -I https://moonbite.org

# Test from external IP
nmap -p 80,443 moonbite.org

# Monitor connections
sudo netstat -tlnp | grep -E ':(80|443)'
```

## Docker-Specific Setup

### Volume Management

```bash
# Create volumes for persistent certs
docker volume create moonbite-certs
docker volume create moonbite-logs

# View volume location
docker inspect moonbite-certs | grep Mountpoint

# Backup certificates
docker run --rm -v moonbite-certs:/certs \
  -v /backup:/backup \
  alpine tar czf /backup/certs-backup.tar.gz -C /certs .
```

### Environment Variables

```bash
# Required for production
-e DOMAIN=moonbite.org
-e LETSENCRYPT_EMAIL=admin@moonbite.org
-e USE_LETSENCRYPT=true

# Optional
-e PORT=5000           # Flask backend port
-e PYTHON_APP=web_app.py
```

### Container Monitoring

```bash
# View logs
docker logs moonbite-web

# Follow logs
docker logs -f moonbite-web

# Check certificate in container
docker exec moonbite-web ls -la /etc/letsencrypt/live/

# Verify certificate
docker exec moonbite-web openssl x509 -in \
  /etc/letsencrypt/live/moonbite.org/fullchain.pem -noout -enddate
```

## Kubernetes Deployment

### Secret Creation

```bash
# Create TLS secret from certificate
kubectl create secret tls moonbite-tls \
  --cert=/etc/letsencrypt/live/moonbite.org/fullchain.pem \
  --key=/etc/letsencrypt/live/moonbite.org/privkey.pem \
  -n moonbite

# Or use a secret volume
kubectl create secret generic letsencrypt-certs \
  --from-file=/etc/letsencrypt/ \
  -n moonbite
```

### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: moonbite-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - moonbite.org
        - www.moonbite.org
      secretName: moonbite-tls
  rules:
    - host: moonbite.org
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: moonbite-web
                port:
                  number: 443
```

### Cert-Manager Automation

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - << 'EOF'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@moonbite.org
    privateKeySecretRef:
      name: letsencrypt-key
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

## Troubleshooting

### Certificate Not Renewing

```bash
# Check certbot logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Test renewal
sudo certbot renew --dry-run --verbose

# Check timer status
sudo systemctl status certbot.timer

# Manual renewal
sudo certbot renew --force-renewal
```

### OCSP Stapling Not Working

```bash
# Verify certificate chain
sudo openssl s_client -connect moonbite.org:443 -tls1_3 -tlsextdebug

# Check resolver
grep resolver /etc/nginx/nginx.conf

# Verify DNS
nslookup ocsp.letsencrypt.org
```

### Port 80 in Use

```bash
# Find process using port 80
sudo lsof -i :80

# Kill process or use different port
sudo kill -9 <PID>

# Or use DNS validation (no port 80 needed)
certbot certonly --dns-<provider> \
  --dns-<provider>-credentials /path/to/credentials
```

### Certificate Verification Failed on iPhone

```bash
# Check certificate details
openssl s_client -connect moonbite.org:443 -showcerts

# Verify full chain
openssl verify -CApath /etc/ssl/certs \
  /etc/letsencrypt/live/moonbite.org/fullchain.pem

# Check on iPhone
# Settings > General > About > Certificate Trust Settings
# Ensure certificate is trusted
```

## Automation Scripts

### Daily Certificate Check Script

```bash
#!/bin/bash
# /opt/monitor-certs.sh

DOMAIN="moonbite.org"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
EMAIL="admin@moonbite.org"

# Check expiration
EXPIRATION=$(openssl x509 -in $CERT_PATH -noout -enddate | cut -d= -f2)
EXPIRATION_EPOCH=$(date -d "$EXPIRATION" +%s)
NOW_EPOCH=$(date +%s)
DAYS_REMAINING=$(( ($EXPIRATION_EPOCH - $NOW_EPOCH) / 86400 ))

echo "[$(date)] Certificate expires in ${DAYS_REMAINING} days"

# Alert if < 30 days
if [ ${DAYS_REMAINING} -lt 30 ]; then
    SUBJECT="ALERT: Certificate expiring in ${DAYS_REMAINING} days"
    echo "Certificate expires on $EXPIRATION" | \
    mail -s "$SUBJECT" $EMAIL
    exit 1
fi

exit 0
```

### Backup Certificates Script

```bash
#!/bin/bash
# /opt/backup-certs.sh

BACKUP_DIR="/backups/certs-$(date +%Y%m%d)"
CERT_DIR="/etc/letsencrypt"

mkdir -p $BACKUP_DIR

# Backup entire letsencrypt directory
tar -czf $BACKUP_DIR/letsencrypt.tar.gz $CERT_DIR

# Keep only last 30 days
find /backups -type d -name "certs-*" -mtime +30 -exec rm -rf {} \;

echo "Certificates backed up to $BACKUP_DIR"
```

## Performance Tuning

### SSL Session Optimization

```nginx
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets off;

# TLS 1.3 specific
ssl_early_data on;
```

### DH Parameter Generation

```bash
# Generate strong DH parameters (takes ~2-5 minutes)
sudo openssl dhparam -out /etc/nginx/dhparam.pem 2048

# Verify
openssl dhparam -text -in /etc/nginx/dhparam.pem
```

## Security Headers

### HSTS (HTTP Strict Transport Security)

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### Preload in HSTS List

Visit: https://hstspreload.org/
- Enter: moonbite.org
- This prevents MITM on first visit

### Certificate Pinning (Advanced)

```nginx
# Public Key Pins (for advanced security)
add_header Public-Key-Pins 'pin-sha256="base64key1"; pin-sha256="base64key2"; max-age=2592000' always;
```

## Migration Guide (Old Domain to New Domain)

```bash
# 1. Get certificate for new domain
sudo certbot certonly --standalone \
  --domains newdomain.org,www.newdomain.org

# 2. Update nginx configuration
sudo nano /etc/nginx/nginx.conf
# Update: server_name and ssl_certificate paths

# 3. Test configuration
sudo nginx -t

# 4. Reload nginx
sudo systemctl reload nginx

# 5. Verify new domain
curl -I https://newdomain.org
```

## Support & Help

```bash
# Certbot documentation
certbot --help

# Check certbot version
certbot --version

# Enable verbose logging
certbot renew --verbose

# Community forum
# https://community.letsencrypt.org/

# Testing with staging (to avoid rate limits)
certbot certonly --staging \
  --domains moonbite.org
```

## Checklist

- [ ] Certificate obtained (Let's Encrypt or CA)
- [ ] nginx configured with SSL
- [ ] Certificate paths correct in nginx.conf
- [ ] Ports 80 and 443 open
- [ ] HSTS header configured
- [ ] OCSP stapling working
- [ ] Certificate renewal automated
- [ ] iPhone can access without warning
- [ ] PWA manifest accessible
- [ ] Service worker registered
- [ ] Backup of certificates created
- [ ] Monitoring/alerts configured

## Next Steps

1. Deploy Docker container with HTTPS
2. Test on real iPhone
3. Monitor certificate expiration
4. Setup automated backups
5. Configure security headers
6. Enable HSTS preload
