#!/usr/bin/env python3
"""MoonBite desktop wallet — a self-contained Tkinter GUI over the local node.

Reads RPC credentials from the node's moonbite.conf and talks JSON-RPC to
moonbited on 127.0.0.1. No third-party packages: standard library only.
Shows balance, a receive address, a send form, and recent transactions, and
refreshes on a timer. It never holds your keys; the node's wallet does.
"""
import base64
import json
import os
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
from tkinter import messagebox, simpledialog, ttk

# ---- MoonBite Reserve Palette (brand spec 2026-08-28) ------------------------
VOID = "#0B0D12"     # primary background
SLATE = "#161A22"    # cards / panels
TERT = "#232833"     # elevated surface, inputs
BONE = "#F5F2EA"     # warm light text, never pure white
ASH = "#8A8580"      # secondary text, labels
ASH2 = "#6E6A66"     # tertiary text
GOLD = "#D9A441"     # the one ownable accent (Moongold)
GOLD_D = "#B8863B"   # gold dark ramp
GOLD_L = "#E8C878"   # gold light ramp
GREEN = "#2E9E6B"    # Gain — functional only
RED = "#C8402F"      # Loss — functional only
CARD = SLATE         # back-compat alias

# Brand fonts: Archivo Black display / Inter body / mono data. On Windows these
# fall back to the brand-specified faces that ship with the OS.
F_DISPLAY = "Arial Black"
F_BODY = "Segoe UI"
F_SEMI = "Segoe UI Semibold"
F_MONO = "Consolas"

DATADIR = os.environ.get("MOONBITE_DATADIR", r"D:\MoonBite")
CONF = os.path.join(DATADIR, "moonbite.conf")
WALLET = "wallet"
START_SCRIPT = os.path.join(DATADIR, "start-mining.ps1")
CREATE_NO_WINDOW = 0x08000000

RADIUS = 10  # brand corner radius


def _round_pts(x1, y1, x2, y2, r):
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    return cv.create_polygon(_round_pts(x1, y1, x2, y2, r), smooth=True,
                             **kw)


def tracked(text, em=0.16):
    """Fake CSS letter-spacing for uppercase labels (Tk has no tracking)."""
    gap = "\u2009" if em < 0.2 else "\u2009\u200a"
    return gap.join(text)


class RoundButton(tk.Canvas):
    """A rounded, flat button in the brand style (gold solid or ghost)."""

    def __init__(self, parent, text, command, ghost=False, bg=SLATE):
        self.fill = SLATE if ghost else GOLD
        self.hover = TERT if ghost else GOLD_L
        self.fg = GOLD if ghost else VOID
        self.ghost = ghost
        f = tkfont.Font(family=F_SEMI, size=10)
        w = f.measure(text) + 36
        h = 34
        super().__init__(parent, width=w, height=h, bg=bg,
                         highlightthickness=0, cursor="hand2")
        self._text = text
        self._cmd = command
        self._font = f
        self._draw(self.fill)
        self.bind("<Enter>", lambda e: self._draw(self.hover))
        self.bind("<Leave>", lambda e: self._draw(self.fill))
        self.bind("<Button-1>", lambda e: command())

    def _draw(self, fill):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        outline = GOLD_D if self.ghost else ""
        round_rect(self, 1, 1, w - 1, h - 1, RADIUS, fill=fill,
                   outline=outline, width=1)
        self.create_text(w / 2, h / 2, text=self._text, fill=self.fg,
                         font=self._font)

    def configure(self, **kw):
        if "text" in kw:
            self._text = kw.pop("text")
            self.config(width=self._font.measure(self._text) + 36)
            self._draw(self.fill)
        if kw:
            super().configure(**kw)
    config = configure


def _read_conf():
    user = pw = None
    port = "9445"
    try:
        with open(CONF, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("rpcuser="):
                    user = line.split("=", 1)[1]
                elif line.startswith("rpcpassword="):
                    pw = line.split("=", 1)[1]
                elif line.startswith("rpcport="):
                    port = line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    return user, pw, port


class Rpc:
    def __init__(self):
        self.user, self.pw, self.port = _read_conf()
        self._id = 0

    def call(self, method, params=None, wallet=True):
        self._id += 1
        url = f"http://127.0.0.1:{self.port}/"
        if wallet:
            url += f"wallet/{WALLET}"
        body = json.dumps({"jsonrpc": "1.0", "id": self._id,
                           "method": method, "params": params or []}).encode()
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", "application/json")
        if self.user is not None:
            tok = base64.b64encode(f"{self.user}:{self.pw}".encode()).decode()
            req.add_header("Authorization", f"Basic {tok}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        if data.get("error"):
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data.get("result")


class RoundedFrame(tk.Canvas):
    """A rounded card: draws a rounded rect and hosts normal widgets on an
    inset inner frame so the rounded corners stay visible."""

    def __init__(self, parent, fill=SLATE, radius=RADIUS, **kw):
        super().__init__(parent, bg=VOID, highlightthickness=0, **kw)
        self.fill = fill
        self.radius = radius
        self.inner = tk.Frame(self, bg=fill)
        self._win = self.create_window(radius, radius, anchor="nw",
                                       window=self.inner)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e):
        self.delete("bg")
        round_rect(self, 1, 1, e.width - 1, e.height - 1, self.radius,
                   fill=self.fill, outline="", tags="bg")
        self.tag_lower("bg")
        self.itemconfig(self._win, width=e.width - 2 * self.radius,
                        height=e.height - 2 * self.radius)


class Wallet(tk.Tk):
    def __init__(self):
        super().__init__()
        self.rpc = Rpc()
        self.title("MoonBite Wallet")
        self.configure(bg=VOID)
        self.geometry("560x620")
        self.minsize(480, 560)
        self._addr = ""
        self._encrypted = False
        self._build()
        self.after(300, self.refresh)
        self._tick()

    # ---- ui ------------------------------------------------------------------
    def _logo(self, parent, size=34):
        """The MoonBite mark: a bone moon with a bite, crossed by two gold bars.
        Replicates the brand SVG (viewBox -140..140) on a canvas."""
        c = tk.Canvas(parent, width=size, height=int(size * 0.9), bg=VOID,
                      highlightthickness=0)
        s = size / 280.0

        def X(x):
            return (x + 140) * s

        def Y(y):
            return (y + 125) * s
        # bone moon (circle r=100) with a void bite (circle r=62, upper-right)
        c.create_oval(X(-100), Y(-100), X(100), Y(100), fill=BONE, outline="")
        c.create_oval(X(8), Y(-132), X(132), Y(-8), fill=VOID, outline="")
        # two moongold bars, wider than the moon
        c.create_rectangle(X(-127), Y(-34), X(127), Y(-21), fill=GOLD,
                           outline="")
        c.create_rectangle(X(-127), Y(18), X(127), Y(31), fill=GOLD,
                           outline="")
        return c

    def _build(self):
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(family=F_BODY, size=10)
        head = tk.Frame(self, bg=VOID)
        head.pack(fill="x", padx=22, pady=(18, 8))
        self._logo(head, 40).pack(side="left", pady=(2,0))
        tk.Label(head, text="MoonBite", bg=VOID, fg=BONE,
                 font=(F_DISPLAY, 15)).pack(side="left", padx=(9, 0))
        self.status = tk.Label(head, text="connecting\u2026", bg=VOID, fg=ASH,
                               font=(F_MONO, 9))
        self.status.pack(side="right", pady=(6, 0))

        card = RoundedFrame(self, height=196)
        card.pack(fill="x", padx=22, pady=(4, 8))
        bal = card.inner
        tk.Label(bal, text=tracked("AVAILABLE BALANCE"), bg=SLATE, fg=ASH,
                 font=(F_BODY, 8)).pack(anchor="w", padx=20, pady=(18, 2))
        row = tk.Frame(bal, bg=SLATE)
        row.pack(anchor="w", padx=20)
        self.bal_lbl = tk.Label(row, text="\u2014", bg=SLATE, fg=BONE,
                                font=(F_DISPLAY, 30))
        self.bal_lbl.pack(side="left")
        tk.Label(row, text="MBITE", bg=SLATE, fg=GOLD,
                 font=(F_SEMI, 11)).pack(side="left", anchor="s", pady=(0, 9),
                                         padx=(9, 0))
        self.sub_lbl = tk.Label(bal, text="", bg=SLATE, fg=ASH,
                                font=(F_BODY, 9))
        self.sub_lbl.pack(anchor="w", padx=20, pady=(0, 8))

        # Security row: encryption status + Encrypt / Unlock button.
        sec = tk.Frame(bal, bg=SLATE)
        sec.pack(fill="x", padx=20, pady=(2, 14))
        self.sec_lbl = tk.Label(sec, text="\U0001F513 not encrypted", bg=SLATE,
                                fg=ASH, font=(F_BODY, 9))
        self.sec_lbl.pack(side="left", pady=(6, 0))
        self.sec_btn = self._btn(sec, "Encrypt wallet", self.encrypt_dialog)
        self.sec_btn.pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=8)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=VOID, borderwidth=0,
                        tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", background=VOID, foreground=ASH,
                        padding=(16, 8), borderwidth=0,
                        font=(F_SEMI, 10))
        style.map("TNotebook.Tab",
                  background=[("selected", SLATE)],
                  foreground=[("selected", GOLD), ("active", BONE)])

        self._build_receive(nb)
        self._build_send(nb)
        self._build_history(nb)

    def _card(self, nb, title):
        rf = RoundedFrame(nb, fill=SLATE)
        nb.add(rf, text=title)
        return rf.inner

    def _build_receive(self, nb):
        f = self._card(nb, "Receive")
        tk.Label(f, text="Your address — share it to receive MBITE", bg=CARD,
                 fg=ASH).pack(anchor="w", padx=16, pady=(16, 6))
        self.addr_var = tk.StringVar(value="\u2014")
        e = tk.Entry(f, textvariable=self.addr_var, bg=TERT, fg=BONE,
                     readonlybackground=TERT, relief="flat",
                     font=(F_MONO, 10), state="readonly")
        e.pack(fill="x", padx=16)
        row = tk.Frame(f, bg=CARD)
        row.pack(anchor="w", padx=16, pady=10)
        self._btn(row, "Copy", self.copy_addr).pack(side="left")
        self._btn(row, "New address", self.new_addr, ghost=True).pack(
            side="left", padx=8)

    def _build_send(self, nb):
        f = self._card(nb, "Send")
        tk.Label(f, text="Recipient address", bg=CARD, fg=ASH).pack(
            anchor="w", padx=16, pady=(16, 2))
        self.to_var = tk.StringVar()
        tk.Entry(f, textvariable=self.to_var, bg=TERT, fg=BONE, relief="flat",
                 insertbackground=BONE, font=(F_MONO, 10)).pack(
            fill="x", padx=16)
        tk.Label(f, text="Amount (MBITE)", bg=CARD, fg=ASH).pack(
            anchor="w", padx=16, pady=(12, 2))
        self.amt_var = tk.StringVar()
        tk.Entry(f, textvariable=self.amt_var, bg=TERT, fg=BONE, relief="flat",
                 insertbackground=BONE, font=(F_BODY, 11)).pack(fill="x", padx=16)
        self._btn(f, "Send", self.send).pack(anchor="w", padx=16, pady=14)
        self.send_msg = tk.Label(f, text="", bg=CARD, fg=ASH, wraplength=460,
                                 justify="left")
        self.send_msg.pack(anchor="w", padx=16)

    def _build_history(self, nb):
        f = self._card(nb, "History")
        self.hist = tk.Text(f, bg=TERT, fg=BONE, relief="flat", height=12,
                            font=(F_MONO, 9), wrap="none", padx=10, pady=8)
        self.hist.pack(fill="both", expand=True, padx=16, pady=16)
        self.hist.configure(state="disabled")

    def _btn(self, parent, text, cmd, ghost=False):
        bg = parent["bg"] if isinstance(parent["bg"], str) else SLATE
        return RoundButton(parent, text, cmd, ghost=ghost, bg=bg)

    # ---- security ------------------------------------------------------------
    def encrypt_dialog(self):
        # If already encrypted, this button unlocks instead.
        if self._encrypted:
            self.unlock_dialog()
            return
        EncryptDialog(self, self._do_encrypt)

    def _do_encrypt(self, passphrase):
        """Runs on a worker thread. The node stops after encryptwallet, so we
        relaunch it via the start script and wait for RPC to return."""
        def work():
            try:
                self.rpc.call("encryptwallet", [passphrase])
            except Exception:  # noqa: BLE001 — node shuts down right after
                pass
            self.status.configure(text="encrypting, node restarting…",
                                  fg=GOLD)
            self._restart_node()
            for _ in range(60):
                try:
                    self.rpc.call("getblockcount", wallet=False)
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(2)
            self.after(0, lambda: messagebox.showinfo(
                "MoonBite",
                "Your wallet is now encrypted. Keep your password safe — "
                "if you lose it, the coins are gone forever.\n\nSending will now "
                "ask you to unlock first."))
            self.refresh()
        threading.Thread(target=work, daemon=True).start()

    def unlock_dialog(self):
        pw = simpledialog.askstring("Unlock wallet",
                                    "Enter your wallet password (unlocks for "
                                    "2 minutes):", show="•", parent=self)
        if not pw:
            return None
        try:
            self.rpc.call("walletpassphrase", [pw, 120])
            self.status.configure(text="wallet unlocked (2 min)", fg=GREEN)
            self.refresh()
            return pw
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("MoonBite", "Wrong password or " + str(e))
            return None

    def _restart_node(self):
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                 "-ExecutionPolicy", "Bypass", "-File", START_SCRIPT],
                creationflags=CREATE_NO_WINDOW)
        except Exception:  # noqa: BLE001
            pass

    # ---- actions -------------------------------------------------------------
    def copy_addr(self):
        if self._addr:
            self.clipboard_clear()
            self.clipboard_append(self._addr)
            self.status.configure(text="address copied", fg=GREEN)

    def new_addr(self):
        def work():
            try:
                a = self.rpc.call("getnewaddress", ["desktop"])
                self._addr = a
                self.addr_var.set(a)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("MoonBite", str(e))
        threading.Thread(target=work, daemon=True).start()

    def send(self):
        to = self.to_var.get().strip()
        amt = self.amt_var.get().strip()
        if not to or not amt:
            self.send_msg.configure(text="Enter an address and amount.", fg=RED)
            return
        try:
            amt_f = float(amt)
        except ValueError:
            self.send_msg.configure(text="Amount must be a number.", fg=RED)
            return
        if not messagebox.askyesno("Confirm send",
                                   f"Send {amt_f} MBITE to\n{to} ?"):
            return

        def work():
            try:
                try:
                    txid = self.rpc.call("sendtoaddress", [to, amt_f])
                except RuntimeError as e:
                    if "passphrase" in str(e).lower() or "locked" in str(e).lower():
                        # Encrypted + locked: ask for the password, unlock, retry.
                        self.send_msg.configure(
                            text="Wallet is locked — unlock to send.", fg=GOLD)
                        pw = self.unlock_dialog()
                        if not pw:
                            return
                        txid = self.rpc.call("sendtoaddress", [to, amt_f])
                    else:
                        raise
                self.send_msg.configure(text=f"Sent. txid {txid[:20]}\u2026",
                                        fg=GREEN)
                self.to_var.set("")
                self.amt_var.set("")
                self.refresh()
            except Exception as e:  # noqa: BLE001
                self.send_msg.configure(text=str(e), fg=RED)
        threading.Thread(target=work, daemon=True).start()

    # ---- refresh -------------------------------------------------------------
    def refresh(self):
        def work():
            try:
                bals = self.rpc.call("getbalances")["mine"]
                info = self.rpc.call("getblockchaininfo", wallet=False)
                mining = self.rpc.call("getmininginfo", wallet=False)
                wi = self.rpc.call("getwalletinfo")
                self._update_security(wi)
                if not self._addr:
                    try:
                        self._addr = self.rpc.call(
                            "getnewaddress", ["desktop"])
                    except Exception:  # noqa: BLE001
                        self._addr = ""
                txs = self.rpc.call("listtransactions", ["*", 15])
            except Exception as e:  # noqa: BLE001
                self.status.configure(text="node offline", fg=RED)
                self.sub_lbl.configure(text=str(e)[:60])
                return
            trusted = bals.get("trusted", 0)
            immature = bals.get("immature", 0)
            pending = bals.get("untrusted_pending", 0)
            self.bal_lbl.configure(text=f"{trusted:,.2f}")
            self.sub_lbl.configure(
                text=f"{immature:,.0f} maturing  \u00b7  {pending:,.2f} pending")
            self.status.configure(
                text=f"height {info['blocks']} \u00b7 "
                     f"{mining.get('networkhashps', 0):,.0f} H/s", fg=GREEN)
            if self._addr:
                self.addr_var.set(self._addr)
            lines = []
            for t in reversed(txs or []):
                cat = t.get("category", "")
                amt = t.get("amount", 0)
                conf = t.get("confirmations", 0)
                when = time.strftime("%m-%d %H:%M",
                                     time.localtime(t.get("time", 0)))
                sign = "+" if amt >= 0 else ""
                tag = {"generate": "mined", "immature": "mined(imm)",
                       "receive": "recv", "send": "sent"}.get(cat, cat)
                lines.append(f"{when}  {tag:<11} {sign}{amt:>12,.2f}  "
                             f"{conf} conf")
            self.hist.configure(state="normal")
            self.hist.delete("1.0", "end")
            self.hist.insert("1.0", "\n".join(lines) or "no transactions yet")
            self.hist.configure(state="disabled")
        threading.Thread(target=work, daemon=True).start()

    def _update_security(self, wi):
        # 'unlocked_until' only exists on an encrypted wallet: 0 = locked,
        # a timestamp = currently unlocked.
        encrypted = "unlocked_until" in wi
        self._encrypted = encrypted

        def apply():
            if not encrypted:
                self.sec_lbl.configure(text="\U0001F513 not encrypted", fg=ASH)
                self.sec_btn.configure(text="Encrypt wallet")
            else:
                until = wi.get("unlocked_until", 0)
                if until and until > time.time():
                    self.sec_lbl.configure(text="\U0001F513 unlocked", fg=GREEN)
                    self.sec_btn.configure(text="Lock")
                else:
                    self.sec_lbl.configure(text="\U0001F512 encrypted", fg=GREEN)
                    self.sec_btn.configure(text="Unlock")
        self.after(0, apply)

    def _tick(self):
        self.refresh()
        self.after(12000, self._tick)


class EncryptDialog(tk.Toplevel):
    """Password + confirmation, with a loss warning. The password is entered
    here and sent straight to the local node; it is never stored or logged."""

    def __init__(self, master, on_ok):
        super().__init__(master)
        self.on_ok = on_ok
        self.title("Encrypt wallet")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        tk.Label(self, text="Set a wallet password", bg=CARD, fg=BONE,
                 font=("Segoe UI Semibold", 13)).pack(anchor="w", padx=20,
                                                      pady=(18, 4))
        tk.Label(self, text="Write it down and keep it safe. If you lose it,\n"
                            "your coins are gone forever — no one can reset it.",
                 bg=CARD, fg=GOLD, justify="left").pack(anchor="w", padx=20)
        self.p1 = self._field("Password")
        self.p2 = self._field("Confirm password")
        self.msg = tk.Label(self, text="", bg=CARD, fg=RED)
        self.msg.pack(anchor="w", padx=20)
        row = tk.Frame(self, bg=CARD)
        row.pack(anchor="e", padx=20, pady=16)
        tk.Button(row, text="Cancel", command=self.destroy, bg=SLATE, fg=BONE,
                  relief="flat", padx=14, pady=6, borderwidth=0).pack(
            side="left", padx=6)
        tk.Button(row, text="Encrypt", command=self._go, bg=GOLD, fg=VOID,
                  relief="flat", font=("Segoe UI Semibold", 10), padx=16,
                  pady=6, borderwidth=0).pack(side="left")
        self.p1.focus_set()

    def _field(self, label):
        tk.Label(self, text=label, bg=CARD, fg=ASH).pack(anchor="w", padx=20,
                                                         pady=(10, 2))
        e = tk.Entry(self, show="•", bg=TERT, fg=BONE, relief="flat",
                     insertbackground=BONE, width=32)
        e.pack(anchor="w", padx=20)
        return e

    def _go(self):
        a, b = self.p1.get(), self.p2.get()
        if len(a) < 8:
            self.msg.configure(text="Use at least 8 characters.")
            return
        if a != b:
            self.msg.configure(text="Passwords do not match.")
            return
        self.on_ok(a)
        self.destroy()


if __name__ == "__main__":
    Wallet().mainloop()
