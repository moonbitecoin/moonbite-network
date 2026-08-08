# MoonBite Production Monitoring Setup

## Overview
Complete monitoring system for MoonBite Production Wallet deployed on Railway.

**Production URL**: https://www.moonbite.org/wallet
**Railway URL**: https://helios-production-5ad6.up.railway.app
**Status Page**: https://status.moonbite.org

---

## 1. Real-Time Monitoring

### Health Check Script
Run continuous production monitoring:

```bash
# One-time health check
python monitoring/health-check.py

# Continuous monitoring (every 5 minutes)
bash monitoring/uptime-monitoring.sh
```

### Monitored Endpoints
✅ Wallet PWA (https://www.moonbite.org/wallet)
✅ Homepage (https://www.moonbite.org/)
✅ HD Wallet API (hd/new endpoint)
✅ Blockchain Status API
✅ SSL Certificate validity
✅ DNS Resolution (69.46.46.28)

---

## 2. Alert Configuration

### Alert Rules (monitoring/alerts.json)

**Critical Alerts** (Immediate Action Required):
- Wallet endpoint down
- API errors > 5%
- Response time > 5 seconds
- Database connection failed
- Memory usage > 90%

**Warning Alerts** (Investigate Within 1 Hour):
- Homepage slow
- Blockchain sync issues
- DNS resolution problems

### Alert Channels
- **Email**: admin@moonbite.org
- **Slack**: (configure webhook in alerts.json)
- **PagerDuty**: (configure integration key for critical incidents)

---

## 3. Railway Platform Monitoring

### Dashboard
- **URL**: https://railway.app (logged in as project owner)
- **Metrics**: CPU, Memory, Disk, Network
- **Logs**: Real-time application logs
- **Deployments**: See all service versions

### Auto-Restart Policy
```json
{
  "restartPolicyType": "ON_FAILURE",
  "restartPolicyMaxRetries": 5
}
```
- Service auto-restarts on crash
- Max 5 restart attempts
- Manual restart available via Railway dashboard

### Health Check Configuration
```json
{
  "endpoint": "/api/blockchain/status",
  "interval": 30,
  "timeout": 10
}
```
Railway pings `/api/blockchain/status` every 30 seconds to verify health.

---

## 4. Performance Metrics

### Track These Metrics
- **CPU Usage**: Target < 70%
- **Memory Usage**: Target < 80%
- **Response Time (p50)**: Target < 500ms
- **Response Time (p95)**: Target < 2s
- **Error Rate**: Target < 1%
- **Request Rate**: Track spikes
- **Database Connections**: Max 10 active

### SLA Targets
- **Uptime**: 99.9% (8.7 hours downtime/month)
- **Response Time**: < 5s (p95)
- **Error Rate**: < 5%

---

## 5. Log Aggregation

### Log Locations
```
Local Logs: ./monitoring/logs/
Railway Logs: https://railway.app > Project > Logs
```

### Log Retention
- Monitoring logs: 30 days
- Railway logs: 7 days (Railway default)
- Archive old logs monthly

### Key Log Patterns to Monitor
```
ERROR: Flask app crashed
ERROR: Database connection failed
ERROR: Out of memory
WARNING: Slow response (> 5s)
INFO: Deployment started
INFO: Service restarted
```

---

## 6. Incident Response

### If Wallet Is Down
1. **Check Status**:
   ```bash
   python monitoring/health-check.py
   ```

2. **Check Railway Dashboard**:
   - Is service running?
   - Is there an error in logs?
   - CPU/Memory at limits?

3. **Check DNS**:
   ```bash
   nslookup www.moonbite.org
   # Should return 69.46.46.28
   ```

4. **Restart Service** (if needed):
   - Via Railway Dashboard: Click "Restart Service"
   - Service auto-restarts on crash

5. **Check Recent Deployments**:
   - Did a new version break something?
   - Rollback to previous version if needed

### If API Is Slow
1. Check memory usage (< 80%)
2. Check active request count
3. Check database connections
4. Check for recent code changes
5. Scale up service if needed (Railway Dashboard)

### If SSL Certificate Expires
- **Expiry Check**:
  ```bash
  openssl s_client -connect www.moonbite.org:443 -servername www.moonbite.org < /dev/null 2>/dev/null | openssl x509 -noout -dates
  ```
- **Renewal**: Let's Encrypt auto-renews (Certbot configured in Dockerfile)
- **Manual Renewal**:
  ```bash
  certbot renew --force-renewal
  ```

---

## 7. Automated Monitoring Setup

### Option A: Linux/Mac Cron Job
```bash
# Edit crontab
crontab -e

# Add this line to run health check every 5 minutes
*/5 * * * * cd /opt/moonbite && python monitoring/health-check.py >> monitoring/logs/health.log 2>&1
```

### Option B: Railway Scheduled Jobs
Coming soon: Railway supports scheduled jobs for monitoring.

### Option C: External Service
Popular options:
- **UptimeRobot** (free tier): https://uptimerobot.com
- **Pingdom** (paid): https://www.pingdom.com
- **StatusPage.io**: Status page + monitoring

---

## 8. Status Page

### Create Public Status Page
```bash
# Option 1: Use StatusPage.io
# Create account, add components, set up monitoring

# Option 2: Self-hosted status page
# Use Cachet or similar open-source solution
```

### Publish Status
- https://status.moonbite.org (public)
- Include: Uptime history, incident log, maintenance windows

---

## 9. Monthly Review

### Every Month:
1. Review uptime metrics
2. Analyze error logs for patterns
3. Check response time trends
4. Update alert thresholds if needed
5. Review incident log
6. Test disaster recovery plan
7. Update monitoring documentation

### Quarterly Deep Dive:
1. Capacity planning (do we need to scale?)
2. Security review (are we logging enough?)
3. Database performance analysis
4. Review failed deployments
5. Update runbooks

---

## 10. Quick Reference

### Emergency Commands
```bash
# Health check
python monitoring/health-check.py

# Test connectivity
curl -I https://www.moonbite.org/wallet

# Check DNS
nslookup www.moonbite.org 8.8.8.8

# View logs
tail -f monitoring/logs/*.log

# Start continuous monitoring
bash monitoring/uptime-monitoring.sh
```

### Important URLs
- **Production**: https://www.moonbite.org/wallet
- **Railway Dashboard**: https://railway.app
- **Namecheap DNS**: https://www.namecheap.com/cp/
- **Status Page**: https://status.moonbite.org
- **GitHub Repo**: https://github.com/moonbitecoin/MoonBite-Coin

### Contacts
- **Admin Email**: admin@moonbite.org
- **Support**: support@moonbite.org
- **Emergency**: (configure PagerDuty)

---

## 11. Next Steps

✅ **Completed**:
- Health check script
- Alert configuration
- Railway integration
- Log setup

📋 **Todo**:
- [ ] Configure email alerts (alerts.json)
- [ ] Set up Slack webhook
- [ ] Create public status page
- [ ] Test incident response procedures
- [ ] Schedule cron jobs for monitoring
- [ ] Configure PagerDuty escalation
- [ ] Document runbooks
- [ ] Train ops team

---

**Last Updated**: 2026-08-08
**Status**: ✅ Production Monitoring Live
