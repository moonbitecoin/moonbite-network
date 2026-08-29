#!/usr/bin/env bash
# Deploy MoonBite wallet updates to DigitalOcean VPS
# Usage: ./deploy-do.sh [VPS_IP]
# Example: ./deploy-do.sh 123.45.67.89

set -euo pipefail

VPS_IP="${1:-}"
if [ -z "$VPS_IP" ]; then
    echo "Usage: $0 <DIGITAL_OCEAN_VPS_IP>"
    echo "Example: $0 123.45.67.89"
    exit 1
fi

APP_DIR="/opt/moonbite-dashboard"
echo "🚀 Deploying MoonBite wallet to DigitalOcean VPS: $VPS_IP"
echo ""

echo "📦 Step 1: Pull latest changes from GitHub..."
ssh root@"$VPS_IP" "cd $APP_DIR && git pull origin main"

echo ""
echo "🔄 Step 2: Restart Flask dashboard service..."
ssh root@"$VPS_IP" "systemctl restart moonbite-dashboard"

echo ""
echo "✅ Step 3: Verify deployment..."
ssh root@"$VPS_IP" "systemctl status moonbite-dashboard --no-pager | head -10"

echo ""
echo "🎉 Deployment complete!"
echo "Visit: https://moonbite.org/wallet-app"
echo ""
echo "Troubleshooting:"
echo "  View logs: ssh root@$VPS_IP systemctl -u moonbite-dashboard -f"
echo "  Restart: ssh root@$VPS_IP systemctl restart moonbite-dashboard"
