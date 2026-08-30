# MoonBite LAN exposure — run ONCE in an ELEVATED PowerShell (Run as Administrator).
# Makes the WSL2 backend (and web build) reachable from phones/computers on your Wi-Fi.
#
# Your Windows LAN IP (phones connect here):  192.168.8.101
# WSL2 IP (backend actually runs here):        auto-detected below (changes on reboot)
#
# Ports:
#   8787 = FastAPI backend
#   8080 = Flutter web build (static server)

$ErrorActionPreference = "Stop"

# Auto-detect the current WSL IP (do NOT hardcode — it changes across restarts).
$wslip = (wsl.exe -d Ubuntu-22.04 -- bash -lc "hostname -I | awk '{print `$1}'").Trim()
Write-Host "WSL IP detected: $wslip"

foreach ($port in 8787, 8080) {
    # Remove any stale mapping, then (re)create it.
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0 2>$null
    netsh interface portproxy add    v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslip
    # Open the Windows Firewall for inbound LAN traffic on this port.
    Remove-NetFirewallRule -DisplayName "MoonBite $port" -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName "MoonBite $port" -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort $port -Profile Private | Out-Null
}

Write-Host ""
Write-Host "Active portproxy rules:"
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "DONE. From any device on your Wi-Fi:"
Write-Host "   Backend API URL : http://192.168.8.101:8787"
Write-Host "   Web app URL     : http://192.168.8.101:8080"
Write-Host ""
Write-Host "NOTE: Re-run this script after a reboot (the WSL IP changes)."
