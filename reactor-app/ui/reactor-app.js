/* MoonBite Reactor — controller.
   Drives the verbatim god-reactor carriers from a real live-chain mining loop.
   Mining = POST /api/mine {address}  (the local launcher proxies to the live
   explorer, so there is no CORS problem and no RPC secret in the client). */
(function () {
    "use strict";

    // ---- carriers the god engine reads every frame ----
    var orb = document.getElementById("miningOrb");
    var elBlocks = document.getElementById("blocksMined");
    var elTotal = document.getElementById("totalBlocks");
    var elFill = document.getElementById("progressBarFill");
    var elHeight = document.getElementById("currentHeight");
    var elElapsed = document.getElementById("elapsedTime");

    // ---- console UI ----
    var form = document.getElementById("rxForm");
    var input = document.getElementById("rxAddress");
    var hint = document.getElementById("rxAddrHint");
    var btnStart = document.getElementById("rxStart");
    var btnStop = document.getElementById("rxStop");
    var statBlocks = document.getElementById("rxStatBlocks");
    var statHeight = document.getElementById("rxStatHeight");
    var statUptime = document.getElementById("rxStatUptime");
    var logfeed = document.getElementById("rxLog");
    var connWrap = document.querySelector(".rx-conn");
    var connText = document.getElementById("rxConnText");

    var ADDR_KEY = "moonbite.reactor.address";

    // ---- state ----
    var mining = false;
    var blocks = 0;
    var startedAt = 0;
    var lastHeight = null;
    var workTarget = 0;   // 0..100 work-meter, snaps on a found block
    var workNow = 0;
    var uptimeTimer = null;
    var meterRaf = null;

    // ---- helpers ----
    function log(msg, cls) {
        var line = document.createElement("span");
        line.className = "rx-logline" + (cls ? " " + cls : "");
        line.innerHTML = msg;
        logfeed.appendChild(line);
        while (logfeed.childNodes.length > 60) logfeed.removeChild(logfeed.firstChild);
        logfeed.scrollTop = logfeed.scrollHeight;
    }
    function setConn(state, text) {
        connWrap.classList.remove("is-online", "is-offline");
        if (state) connWrap.classList.add(state);
        connText.textContent = text;
    }
    // Basic client-side sanity only — the node is the real validator.
    function looksLikeAddress(a) {
        a = (a || "").trim();
        if (a.length < 20 || a.length > 120) return false;
        if (/^(moon1|tmoon1|rmoon1)/.test(a)) return true;   // bech32
        if (/^[M23][1-9A-HJ-NP-Za-km-z]{20,}$/.test(a)) return true; // base58 P2PKH/P2SH
        return false;
    }
    function fmtElapsed(sec) {
        var m = Math.floor(sec / 60), s = sec % 60;
        return m > 0 ? m + "m " + s + "s" : s + "s";
    }

    // ---- work meter: smooth ramp toward workTarget, mirrored into the beam ----
    function meterLoop() {
        workNow += (workTarget - workNow) * 0.08;
        if (Math.abs(workTarget - workNow) < 0.1) workNow = workTarget;
        elFill.style.width = workNow.toFixed(1) + "%";
        // while mining and not at a snap, keep creeping so it feels alive
        if (mining && workTarget < 92) workTarget = Math.min(92, workTarget + 0.25);
        meterRaf = requestAnimationFrame(meterLoop);
    }

    // ---- the mining loop ----
    function mineRound() {
        if (!mining) return;
        fetch("/api/mine", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ address: input.value.trim() })
        }).then(function (r) {
            return r.json().then(function (body) { return { ok: r.ok, body: body }; });
        }).then(function (res) {
            if (!mining) return;
            setConn("is-online", "online");
            var b = res.body || {};

            if (b.error) {
                log("node: " + b.error, "is-bad");
                // A bad address / disabled node will not self-heal — stop cleanly.
                if (/invalid|disabled|demo/i.test(b.error)) { stop("node rejected: " + b.error); return; }
                setTimeout(mineRound, 1500);
                return;
            }

            if (b.found) {
                blocks += 1;
                workTarget = 100; workNow = 100;          // snap the beam
                setTimeout(function () { if (mining) { workTarget = 0; workNow = 0; } }, 220);
                var h = (b.height != null) ? b.height : (lastHeight != null ? lastHeight + 1 : "?");
                lastHeight = (typeof h === "number") ? h : lastHeight;
                var hash = (b.hashes && b.hashes[0]) ? b.hashes[0] : "";
                var shortHash = hash ? (hash.slice(0, 10) + "…" + hash.slice(-6)) : "";
                // update carriers (god engine flashes burst on blocksMined++)
                elBlocks.textContent = blocks;
                elHeight.textContent = h;
                elTotal.textContent = blocks;
                statBlocks.textContent = blocks;
                statHeight.textContent = h;
                log("+ block <b>#" + h + "</b> mined" + (shortHash ? "  " + shortHash : ""), "is-hit");
            } else {
                log("… no block this round, retrying");
            }
            setTimeout(mineRound, 250);
        }).catch(function (err) {
            if (!mining) return;
            setConn("is-offline", "offline");
            log("connection lost — retrying (" + (err && err.message || "error") + ")", "is-bad");
            setTimeout(mineRound, 2500);
        });
    }

    // ---- start / stop ----
    function start() {
        var addr = input.value.trim();
        if (!looksLikeAddress(addr)) {
            input.classList.add("is-bad");
            hint.classList.add("is-bad");
            hint.textContent = "That doesn't look like a MoonBite address (moon1… or M…).";
            input.focus();
            return;
        }
        input.classList.remove("is-bad");
        hint.classList.remove("is-bad");
        hint.textContent = "Blocks you mine pay their reward straight to this address.";
        try { localStorage.setItem(ADDR_KEY, addr); } catch (e) {}

        mining = true;
        blocks = 0; lastHeight = null; workTarget = 0; workNow = 0;
        startedAt = Date.now();
        elBlocks.textContent = "0";
        elTotal.textContent = "0";
        statBlocks.textContent = "0";
        orb.classList.remove("idle");        // → god engine goes REACTOR ONLINE

        btnStart.hidden = true;
        btnStop.hidden = false;
        input.disabled = true;
        setConn("is-online", "reactor online");
        log("⚡ reactor ignition — mining to <b>" + addr.slice(0, 6) + "…" + addr.slice(-4) + "</b>", "is-good");

        uptimeTimer = setInterval(function () {
            var sec = Math.floor((Date.now() - startedAt) / 1000);
            var t = fmtElapsed(sec);
            statUptime.textContent = t;
            elElapsed.textContent = t;
        }, 500);
        meterLoop();
        mineRound();
    }

    function stop(reason) {
        if (!mining) return;
        mining = false;
        orb.classList.add("idle");           // → god engine returns to STANDBY
        if (uptimeTimer) { clearInterval(uptimeTimer); uptimeTimer = null; }
        if (meterRaf) { cancelAnimationFrame(meterRaf); meterRaf = null; }
        workTarget = 0; workNow = 0; elFill.style.width = "0%";
        btnStart.hidden = false;
        btnStop.hidden = true;
        input.disabled = false;
        setConn("", "idle");
        log(reason ? "■ powered down — " + reason : "■ reactor powered down. " + blocks + " block(s) this session.", "is-bad");
    }

    // ---- wiring ----
    form.addEventListener("submit", function (e) { e.preventDefault(); start(); });
    btnStop.addEventListener("click", function () { stop(); });
    input.addEventListener("input", function () {
        input.classList.remove("is-bad"); hint.classList.remove("is-bad");
    });
    btnStart.addEventListener("mousemove", function (e) {
        var rect = btnStart.getBoundingClientRect();
        btnStart.style.setProperty("--mx", (e.clientX - rect.left) + "px");
    });

    // restore saved address
    try {
        var saved = localStorage.getItem(ADDR_KEY);
        if (saved) input.value = saved;
    } catch (e) {}

    // reachability ping (best-effort; the launcher exposes /api/health)
    fetch("/api/health").then(function (r) { return r.json(); }).then(function (h) {
        setConn("is-online", "explorer reachable");
        if (h && h.height != null) { statHeight.textContent = h.height; elHeight.textContent = h.height; }
    }).catch(function () {
        setConn("is-offline", "explorer offline");
    });

    log("MoonBite Reactor ready. Enter your address and fire the core.");
})();
