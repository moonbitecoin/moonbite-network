#!/bin/bash
# MoonBite Production Uptime Monitoring
# Runs continuous health checks and logs results
# Usage: ./uptime-monitoring.sh

LOG_DIR="./monitoring/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/monitoring_$TIMESTAMP.log"

echo "Starting MoonBite Production Monitoring"
echo "Logging to: $LOG_FILE"

# Run health checks every 5 minutes
while true; do
    echo "" >> "$LOG_FILE"
    echo "=== Check at $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_FILE"

    # Test Wallet Endpoint
    echo -n "Wallet PWA: " >> "$LOG_FILE"
    if curl -s -f https://www.moonbite.org/wallet -o /dev/null -w "%{http_code}\n"; then
        echo "OK" >> "$LOG_FILE"
    else
        echo "FAILED" >> "$LOG_FILE"
    fi

    # Test Homepage
    echo -n "Homepage: " >> "$LOG_FILE"
    if curl -s -f https://www.moonbite.org/ -o /dev/null -w "%{http_code}\n"; then
        echo "OK" >> "$LOG_FILE"
    else
        echo "FAILED" >> "$LOG_FILE"
    fi

    # Test API
    echo -n "HD Wallet API: " >> "$LOG_FILE"
    if curl -s -f https://helios-production-5ad6.up.railway.app/api/wallet/hd/new -o /dev/null -w "%{http_code}\n"; then
        echo "OK" >> "$LOG_FILE"
    else
        echo "FAILED" >> "$LOG_FILE"
    fi

    # Test DNS
    echo -n "DNS Resolution: " >> "$LOG_FILE"
    if nslookup www.moonbite.org 8.8.8.8 | grep -q "69.46.46.28"; then
        echo "OK (69.46.46.28)" >> "$LOG_FILE"
    else
        echo "FAILED" >> "$LOG_FILE"
    fi

    # Wait 5 minutes before next check
    sleep 300
done
