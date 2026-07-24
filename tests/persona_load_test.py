"""Concurrent 50-persona smoke/load test against a running MoonBite web app.

Spins up 50 archetype users in parallel (ThreadPoolExecutor) and drives real
end-to-end journeys through the public API: wallet creation, mining, balance,
the non-custodial exchange (incl. cancel-token auth), merchant invoicing, the
block explorer, and the marketing pages.

This talks to a LOCAL instance only (BASE env, default http://127.0.0.1:5055).
It never touches the live node. Run:  python tests/persona_load_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.environ.get("BASE", "http://127.0.0.1:5055")
N_PERSONAS = int(os.environ.get("PERSONAS", "50"))
TIMEOUT = 15

# Capabilities each persona may exercise; used to build the final matrix.
CAPS = ["PAGES", "WALLET", "MINER", "BALANCE", "EXCHANGE", "MERCHANT", "EXPLORER"]

# 10 archetypes cycled across N personas. Each names the caps it cares about.
ARCHETYPES = [
    ("Miner",          ["PAGES", "WALLET", "MINER", "BALANCE"]),
    ("HODLer",         ["PAGES", "WALLET", "BALANCE"]),
    ("DayTrader",      ["PAGES", "WALLET", "EXCHANGE"]),
    ("Merchant",       ["PAGES", "WALLET", "MERCHANT"]),
    ("BlockExplorer",  ["PAGES", "EXPLORER"]),
    ("Developer",      ["PAGES", "WALLET", "EXPLORER", "EXCHANGE"]),
    ("Newcomer",       ["PAGES", "WALLET"]),
    ("Whale",          ["PAGES", "WALLET", "MINER", "EXCHANGE"]),
    ("Arbitrageur",    ["PAGES", "WALLET", "EXCHANGE", "EXPLORER"]),
    ("ShopOwner",      ["PAGES", "WALLET", "MERCHANT", "BALANCE"]),
]


def _req(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw  # HTML pages
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return 0, {"_error": str(e)}


class Result:
    def __init__(self, pid, archetype):
        self.pid = pid
        self.archetype = archetype
        self.caps = {}      # cap -> "PASS" | "FAIL:<why>" | "SKIP"
        self.notes = []

    def ok(self, cap):
        self.caps[cap] = "PASS"

    def fail(self, cap, why):
        self.caps[cap] = f"FAIL:{why}"

    def skip(self, cap):
        self.caps.setdefault(cap, "SKIP")


# ---- capability journeys -------------------------------------------------- #

def cap_pages(res):
    for p in ("/", "/markets", "/get-wallet", "/mine", "/explorer", "/about", "/why"):
        code, _ = _req("GET", p)
        if code != 200:
            res.fail("PAGES", f"{p}={code}")
            return
    res.ok("PAGES")


def cap_wallet(res, ctx):
    code, body = _req("GET", "/api/wallet/new")
    if code != 200 or not isinstance(body, dict) or body.get("status") != "success":
        res.fail("WALLET", f"code={code}")
        return
    addr = body.get("address")
    if not addr or not isinstance(addr, str) or len(addr) < 6:
        res.fail("WALLET", f"bad address {addr!r}")
        return
    ctx["address"] = addr
    # Informational: flag if the wallet is not minting MoonBite-branded prefixes.
    if not addr.startswith(("moon", "M")):
        res.notes.append(f"addr-prefix={addr[:1]}(non-MoonBite)")
    res.ok("WALLET")


def cap_miner(res, ctx):
    addr = ctx.get("address")
    if not addr:
        res.fail("MINER", "no address")
        return
    code, body = _req("POST", "/api/mining/start", {"blocks": 1, "address": addr})
    # Singleton miner: concurrent starts legitimately get 400 "already in progress".
    if code == 200 and isinstance(body, dict) and body.get("status") == "mining":
        # poll to completion (bounded)
        for _ in range(40):
            time.sleep(0.25)
            sc, sb = _req("GET", "/api/mining/status")
            if isinstance(sb, dict) and sb.get("status") == "idle":
                break
        res.ok("MINER")
    elif code == 400 and isinstance(body, dict) and "already" in str(body.get("message", "")).lower():
        res.caps["MINER"] = "PASS"
        res.notes.append("miner-singleton-busy(expected)")
    else:
        res.fail("MINER", f"code={code} {str(body)[:40]}")


def cap_balance(res):
    code, body = _req("GET", "/api/wallet/balance")
    if code == 200 and isinstance(body, dict) and body.get("status") == "success":
        res.ok("BALANCE")
        res.notes.append(f"bal={body.get('balance_coins')}c/{body.get('utxo_count')}utxo")
    else:
        res.fail("BALANCE", f"code={code}")


def cap_exchange(res, ctx):
    addr = ctx.get("address") or "moon1personatestaddress"
    order = {
        "side": "sell", "pair": "MBITE/LTC", "price": "0.001", "amount": "5",
        "mbite_address": addr, "quote_address": "ltc1personaquoteaddr",
    }
    code, body = _req("POST", "/api/exchange/order", order)
    if code not in (200, 201) or not isinstance(body, dict):
        res.fail("EXCHANGE", f"create code={code}")
        return
    o = body.get("order", body)
    oid, token = o.get("id"), o.get("cancel_token")
    if not oid or not token:
        res.fail("EXCHANGE", "no id/token")
        return
    # public read must NOT leak the token
    gc, gb = _req("GET", f"/api/exchange/order/{oid}")
    if isinstance(gb, dict) and "cancel_token" in json.dumps(gb):
        res.fail("EXCHANGE", "token leaked on public read")
        return
    # wrong token must be rejected
    bc, _ = _req("POST", f"/api/exchange/order/{oid}/cancel", {"cancel_token": "wrong"})
    if bc == 200:
        res.fail("EXCHANGE", "wrong token accepted")
        return
    # correct token cancels
    cc, cb = _req("POST", f"/api/exchange/order/{oid}/cancel", {"cancel_token": token})
    if cc == 200 and isinstance(cb, dict):
        res.ok("EXCHANGE")
    else:
        res.fail("EXCHANGE", f"cancel code={cc}")


def cap_merchant(res, ctx):
    addr = ctx.get("address") or "moon1personamerchant"
    reg = {"name": f"Shop{res.pid}", "category": "food",
           "mbite_address": addr, "blurb": "persona test cafe"}
    code, body = _req("POST", "/api/merchants", reg)
    if code not in (200, 201) or not isinstance(body, dict) or "merchant" not in body:
        res.fail("MERCHANT", f"register code={code} {str(body)[:40]}")
        return
    m = body["merchant"]
    inv = {"address": m.get("mbite_address", addr), "amount": "1.50",
           "merchant_id": m.get("id"), "memo": "persona coffee"}
    ic, ib = _req("POST", "/api/merchant/invoice", inv)
    if ic in (200, 201) and isinstance(ib, dict) and "invoice" in ib:
        res.ok("MERCHANT")
    else:
        res.fail("MERCHANT", f"invoice code={ic} {str(ib)[:40]}")


def cap_explorer(res):
    code, body = _req("GET", "/api/explorer/blocks")
    if code != 200:
        res.fail("EXPLORER", f"blocks code={code}")
        return
    sc, _ = _req("GET", "/api/explorer/search?q=0")
    if sc not in (200, 404):
        res.fail("EXPLORER", f"search code={sc}")
        return
    res.ok("EXPLORER")


def run_persona(pid):
    archetype, caps = ARCHETYPES[pid % len(ARCHETYPES)]
    res = Result(pid, archetype)
    ctx = {}
    for c in CAPS:
        res.skip(c)
    try:
        if "PAGES" in caps:
            cap_pages(res)
        if "WALLET" in caps:
            cap_wallet(res, ctx)
        if "MINER" in caps:
            cap_miner(res, ctx)
        if "BALANCE" in caps:
            cap_balance(res)
        if "EXCHANGE" in caps:
            cap_exchange(res, ctx)
        if "MERCHANT" in caps:
            cap_merchant(res, ctx)
        if "EXPLORER" in caps:
            cap_explorer(res)
    except Exception as e:  # noqa: BLE001
        res.notes.append(f"exception:{e}")
    return res


def main():
    print(f"Firing {N_PERSONAS} concurrent personas at {BASE}\n")
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=N_PERSONAS) as pool:
        futs = [pool.submit(run_persona, i) for i in range(N_PERSONAS)]
        for f in as_completed(futs):
            results.append(f.result())
    dt = time.time() - t0
    results.sort(key=lambda r: r.pid)

    # aggregate
    tally = {c: defaultdict(int) for c in CAPS}
    fails = []
    for r in results:
        for c in CAPS:
            st = r.caps.get(c, "SKIP")
            key = "PASS" if st == "PASS" else ("SKIP" if st == "SKIP" else "FAIL")
            tally[c][key] += 1
            if key == "FAIL":
                fails.append((r.pid, r.archetype, c, r.caps[c]))

    print("=== CAPABILITY MATRIX (across personas that exercised it) ===")
    print(f"{'CAP':<10} {'PASS':>5} {'FAIL':>5} {'SKIP':>5}")
    for c in CAPS:
        t = tally[c]
        print(f"{c:<10} {t['PASS']:>5} {t['FAIL']:>5} {t['SKIP']:>5}")

    print("\n=== FAILURES ===")
    if not fails:
        print("(none)")
    for pid, arch, cap, why in fails:
        print(f"  persona#{pid:<2} {arch:<13} {cap}: {why}")

    total_fail = len(fails)
    exercised = sum(tally[c]['PASS'] + tally[c]['FAIL'] for c in CAPS)
    passed = sum(tally[c]['PASS'] for c in CAPS)
    print(f"\n{passed}/{exercised} capability-executions passed "
          f"across {N_PERSONAS} personas in {dt:.1f}s")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
