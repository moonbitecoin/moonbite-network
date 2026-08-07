# 🚀 MoonBite PWA Wallet - Railway Deployment Guide

## Quick Start (5 Minutes)

### Step 1: Connect GitHub Repository
```bash
# Push your code to GitHub
git push origin main
```

1. Go to [Railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub"
3. Select your `moonbitecoin/MoonBite-Coin` repository
4. Railway will auto-detect and build

### Step 2: Set Environment Variables

In Railway Dashboard → Project → Variables:

```
RAILWAY_DOMAIN=moonbite.org
LETSENCRYPT_EMAIL=admin@moonbite.org
PORT=443
FLASK_PORT=5000
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
TRUSTED_PROXY_COUNT=1
```

### Step 3: Configure Domain

1. In Railway → Plugins → add **PostgreSQL** (optional, for persistence)
2. Go to Networking → Custom Domain
3. Add `moonbite.org`
4. Railway provides free HTTPS certificate ✅

### Step 4: Deploy

Railway auto-deploys when you push to GitHub. Or click "Deploy" in Dashboard.

### Step 5: Test

```bash
# Wait 2-3 minutes for build/deployment
curl https://moonbite.org/wallet

# Or visit in browser
open https://moonbite.org/wallet
```

---

## 📱 iPhone Installation

1. Open Safari → `https://moonbite.org`
2. Tap Share button (bottom)
3. Tap "Add to Home Screen"
4. Name: "MoonBite Wallet"
5. Tap Add → Opens like native app!

---

## 🤖 Android Installation

1. Open Chrome → `https://moonbite.org`
2. Tap Menu (3 dots)
3. Tap "Install app"
4. Tap Install → Adds to home screen!

---

## 🛡️ Security Checklist

✅ **HTTPS/TLS**
- Railway provides free SSL certificates
- Auto-renewal included
- TLS 1.2/1.3 enforced

✅ **Headers**
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

✅ **Service Worker**
- Offline-first caching
- Auto-updates every 24h
- Network fallback

---

## 🔧 Troubleshooting

### "Certificate not trusted on iPhone"
**Solution:**
1. Railway handles certificates automatically
2. If using custom domain, add CNAME to DNS
3. Wait 15 minutes for propagation
4. Clear Safari cache: Settings → Safari → Clear History

### "App won't install on iPhone"
**Solution:**
1. Must be HTTPS (Railway provides this)
2. Manifest.json must be accessible
3. App icons must be 192x192 or larger
4. Try in different Safari tab

### "Offline mode not working"
**Solution:**
1. Service Worker needs HTTPS
2. First load caches assets
3. Subsequent loads work offline
4. Check browser DevTools → Application → Service Workers

### "Too many redirects"
**Solution:**
1. Disable CloudFlare if using
2. Set `TRUSTED_PROXY_COUNT=1` for Railway
3. Clear browser cache

---

## 📊 Monitoring

### Railway Dashboard
- View logs: "Logs" tab
- Monitor usage: "Metrics" tab
- Check health: "Health" indicator

### View Logs
```bash
# Via Railway CLI
railway logs

# Or in Dashboard → Logs tab
```

### Check Service Status
```bash
curl -v https://moonbite.org/wallet
```

---

## 🔄 Auto-Deployment

Railway auto-deploys on every GitHub push:

```bash
# Make changes locally
git add .
git commit -m "Update wallet features"
git push origin main

# Railway automatically:
# 1. Detects the push
# 2. Builds Docker image
# 3. Tests health checks
# 4. Deploys to production
# 5. Zero-downtime update
```

---

## 💾 Database (Optional)

To add persistent storage:

1. Railway Dashboard → Plugins → PostgreSQL
2. Copy connection string
3. Set `DATABASE_URL` environment variable
4. Update `web_app.py` to use PostgreSQL

---

## 🚀 Production Optimization

### Enable Caching
Add to environment variables:
```
CACHE_TTL=3600
CDN_ENABLED=true
```

### Scale Resources
In Railway → Settings → Plan:
- Increase Memory if needed
- Add more CPU for concurrent users

### Custom Domain + Email
```bash
# Use custom domain
railway domain moonbite.org

# Set SSL/TLS
railway ssl auto
```

---

## 📈 Performance Monitoring

Check Lighthouse scores:

```bash
# Install Lighthouse
npm install -g lighthouse

# Test your site
lighthouse https://moonbite.org --view
```

Expected scores:
- Performance: 90+
- Accessibility: 95+
- Best Practices: 95+
- SEO: 100

---

## 🆘 Support

**Railway Docs:** https://docs.railway.app
**Railway Status:** https://status.railway.app
**Support Chat:** https://railway.app/chat (in dashboard)

---

## ✅ Deployment Checklist

- [ ] GitHub repository connected
- [ ] Environment variables set
- [ ] Custom domain configured (optional)
- [ ] HTTPS certificate verified
- [ ] Health checks passing
- [ ] iPhone installation tested
- [ ] Android installation tested
- [ ] Offline mode verified
- [ ] Logs checked for errors
- [ ] Performance Lighthouse tested

---

## 🎉 Success!

Your MoonBite PWA Wallet is now live on Railway!

**HTTPS:** https://moonbite.org ✅
**iPhone App:** Add to Home Screen ✅
**Android App:** Install from menu ✅
**Offline Support:** Works without internet ✅

Happy mining! 🌙⛏️
