#!/usr/bin/env python3
"""MoonBite Reactor — desktop launcher (standard library only).

Serves the cinematic reactor UI locally and proxies mining requests to the
live MoonBite explorer. Proof-of-work runs on the network node; this app only
supplies the reward address and renders the god-reactor. No dependencies, no
RPC credentials, nothing leaves the machine except a mine request to the
public explorer you point it at.

Usage:
    python moonbite_reactor.py                 # open the app window
    python moonbite_reactor.py --no-browser    # serve only (for testing)
    python moonbite_reactor.py --port 7801
    python moonbite_reactor.py --explorer https://your-node.example
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_EXPLORER = "https://moonbite-production.up.railway.app"
EXPLORER = DEFAULT_EXPLORER  # overridden by --explorer / env


def _ui_dir():
    """Locate the bundled ui/ folder (works frozen via PyInstaller and from source)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ui")


UI_DIR = _ui_dir()
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


def _proxy_mine(payload, timeout=90):
    """Forward a mine request to the live explorer. Returns (status, body-bytes)."""
    url = EXPLORER.rstrip("/") + "/api/mine"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return 502, json.dumps({"error": f"cannot reach explorer ({reason})"}).encode("utf-8")


def _health():
    """Lightweight reachability probe against the explorer root."""
    url = EXPLORER.rstrip("/") + "/"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"ok": True, "explorer": EXPLORER, "height": None, "status": resp.status}
    except Exception as exc:  # noqa: BLE001 - reachability only, any failure = offline
        return {"ok": False, "explorer": EXPLORER, "error": str(getattr(exc, "reason", exc))}


class Handler(BaseHTTPRequestHandler):
    server_version = "MoonBiteReactor/1.0"

    def log_message(self, *_args):
        pass  # keep the console clean

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._send(200, json.dumps(_health()))
            return
        self._serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/mine":
            length = int(self.headers.get("Content-Length", 0) or 0)
            payload = self.rfile.read(length) if length else b"{}"
            status, body = _proxy_mine(payload)
            self._send(status, body)
            return
        self._send(404, json.dumps({"error": "not found"}))

    def _serve_static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        # prevent path traversal
        full = os.path.normpath(os.path.join(UI_DIR, rel))
        if not full.startswith(os.path.normpath(UI_DIR)):
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        if not os.path.isfile(full):
            self._send(404, json.dumps({"error": "not found"}))
            return
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as fh:
            data = fh.read()
        self._send(200, data, _MIME.get(ext, "application/octet-stream"))


def _open_app_window(url):
    """Open a chrome-less app window if Edge/Chrome is available, else default browser."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    profile = os.path.join(
        os.path.expandvars(r"%LocalAppData%") or os.getcwd(), "MoonBiteReactor", "profile"
    )
    for exe in candidates:
        if exe and os.path.isfile(exe):
            try:
                os.spawnv(os.P_NOWAIT, exe, [
                    exe,
                    "--app=" + url,
                    "--window-size=1180,760",
                    "--user-data-dir=" + profile,
                    "--no-first-run",
                    "--no-default-browser-check",
                ])
                return True
            except Exception:  # noqa: BLE001 - fall through to default browser
                pass
    webbrowser.open(url)
    return False


def main(argv=None):
    global EXPLORER
    p = argparse.ArgumentParser(description="MoonBite Reactor desktop launcher")
    p.add_argument("--port", type=int, default=int(os.environ.get("REACTOR_PORT", "7801")))
    p.add_argument("--explorer", default=os.environ.get("MOONBITE_EXPLORER", DEFAULT_EXPLORER))
    p.add_argument("--no-browser", action="store_true", help="serve only; do not open a window")
    args = p.parse_args(argv)
    EXPLORER = args.explorer.rstrip("/")

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    host, port = httpd.server_address
    url = f"http://127.0.0.1:{port}/"

    print("=" * 56)
    print(" MoonBite Reactor")
    print("=" * 56)
    print(f" UI        : {url}")
    print(f" Explorer  : {EXPLORER}")
    print(f" UI files  : {UI_DIR}")
    print("-" * 56)

    if not args.no_browser:
        threading.Thread(
            target=lambda: (time.sleep(0.4), _open_app_window(url)), daemon=True
        ).start()
        print(" Opening app window… (close this console to quit)")
    else:
        print(" Serving (no browser). Ctrl+C to quit.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n Reactor offline.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
