"""
MoonBite Production Monitoring System
Monitors wallet uptime, API endpoints, database health, and performance
"""

import requests
import json
import time
from datetime import datetime
import sys

class MoonBiteMonitoring:
    def __init__(self):
        self.base_url = "https://www.moonbite.org"
        self.railway_url = "https://helios-production-5ad6.up.railway.app"
        self.results = {}

    def check_wallet_endpoint(self):
        """Check if wallet PWA loads"""
        try:
            response = requests.get(
                f"{self.base_url}/wallet",
                timeout=10,
                allow_redirects=True
            )
            if response.status_code == 200 and "MoonBite Wallet" in response.text:
                return {"status": "PASS", "code": 200, "load_time": f"{response.elapsed.total_seconds():.2f}s"}
            else:
                return {"status": "FAIL", "code": response.status_code}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}

    def check_homepage(self):
        """Check if homepage loads"""
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=10
            )
            if response.status_code == 200:
                return {"status": "PASS", "code": 200, "load_time": f"{response.elapsed.total_seconds():.2f}s"}
            else:
                return {"status": "FAIL", "code": response.status_code}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}

    def check_api_wallet_hd_new(self):
        """Check wallet HD creation endpoint"""
        try:
            response = requests.get(
                f"{self.railway_url}/api/wallet/hd/new",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if "mnemonic" in data:
                    word_count = len(data["mnemonic"].split())
                    return {"status": "PASS", "code": 200, "mnemonic_words": word_count}
            return {"status": "FAIL", "code": response.status_code}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}

    def check_api_blockchain_status(self):
        """Check blockchain status endpoint"""
        try:
            response = requests.get(
                f"{self.railway_url}/api/blockchain/status",
                timeout=10
            )
            if response.status_code == 200:
                return {"status": "PASS", "code": 200}
            else:
                return {"status": "FAIL", "code": response.status_code}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}

    def check_ssl_certificate(self):
        """Check SSL certificate validity"""
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=10
            )
            if response.status_code == 200 and response.url.startswith("https"):
                return {"status": "PASS", "ssl": "Valid HTTPS"}
            else:
                return {"status": "FAIL", "ssl": "Invalid"}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}

    def check_dns_resolution(self):
        """Check DNS resolution"""
        import socket
        try:
            ip = socket.gethostbyname("www.moonbite.org")
            expected_ip = "69.46.46.28"
            if ip == expected_ip:
                return {"status": "PASS", "ip": ip}
            else:
                return {"status": "WARNING", "ip": ip, "expected": expected_ip}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}

    def run_all_checks(self):
        """Run all monitoring checks"""
        print("=" * 70)
        print(f"MOONBITE PRODUCTION MONITORING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        checks = {
            "Wallet PWA Endpoint": self.check_wallet_endpoint(),
            "Homepage": self.check_homepage(),
            "HD Wallet API": self.check_api_wallet_hd_new(),
            "Blockchain Status API": self.check_api_blockchain_status(),
            "SSL Certificate": self.check_ssl_certificate(),
            "DNS Resolution": self.check_dns_resolution(),
        }

        self.results = checks

        # Print results
        for check_name, result in checks.items():
            status = result.get("status", "UNKNOWN")
            print(f"\n{check_name}: {status}")
            for key, value in result.items():
                if key != "status":
                    print(f"  {key}: {value}")

        # Summary
        print("\n" + "=" * 70)
        pass_count = sum(1 for r in checks.values() if r.get("status") == "PASS")
        total_count = len(checks)
        print(f"SUMMARY: {pass_count}/{total_count} checks passed")

        if pass_count == total_count:
            print("SUCCESS: All systems operational")
        elif pass_count >= total_count - 1:
            print("WARNING: Minor issues detected")
        else:
            print("CRITICAL: Investigate immediately")

        print("=" * 70)

        return checks

if __name__ == "__main__":
    monitor = MoonBiteMonitoring()
    monitor.run_all_checks()
