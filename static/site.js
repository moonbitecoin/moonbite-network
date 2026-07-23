/* ==========================================================================
   MoonBite — Marketing Site behaviour (site.js)
   Loaded with `defer` by base.html on every page. Self-contained IIFE.
   Does NOT declare `htmlElement` / `themeToggle` — those live in base's
   inline theme script. Everything here is feature-detected so it is safe to
   load on the tool pages too (dashboard/wallet/mining/explorer).
   ========================================================================== */
(function () {
    "use strict";

    /* ------------------------------------------------ mega-nav dropdowns */
    var navItems = document.querySelectorAll(".mb-nav-item");
    navItems.forEach(function (item) {
        var trigger = item.querySelector(".mb-nav-trigger");
        if (!trigger || !item.querySelector(".mb-dropdown")) return;
        // Click toggles (works on touch + keyboard); hover handled by CSS.
        trigger.addEventListener("click", function (e) {
            // Allow plain links without a dropdown to navigate normally.
            e.preventDefault();
            var wasOpen = item.classList.contains("is-open");
            closeAllDropdowns();
            if (!wasOpen) item.classList.add("is-open");
        });
    });
    function closeAllDropdowns() {
        navItems.forEach(function (i) { i.classList.remove("is-open"); });
    }
    document.addEventListener("click", function (e) {
        if (!e.target.closest(".mb-nav-item")) closeAllDropdowns();
    });
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { closeAllDropdowns(); closeMobileSheet(); }
    });

    /* ------------------------------------------------ mobile sheet */
    var hamburger = document.querySelector(".mb-hamburger");
    var sheet = document.querySelector(".mb-mobile-sheet");
    var sheetClose = document.querySelector(".mb-mobile-close");
    function openMobileSheet() { if (sheet) { sheet.classList.add("is-open"); document.body.style.overflow = "hidden"; } }
    function closeMobileSheet() { if (sheet) { sheet.classList.remove("is-open"); document.body.style.overflow = ""; } }
    if (hamburger) hamburger.addEventListener("click", openMobileSheet);
    if (sheetClose) sheetClose.addEventListener("click", closeMobileSheet);
    document.querySelectorAll(".mb-mobile-group > button").forEach(function (btn) {
        btn.addEventListener("click", function () { btn.parentElement.classList.toggle("is-open"); });
    });
    document.querySelectorAll(".mb-mobile-links a").forEach(function (a) {
        a.addEventListener("click", closeMobileSheet);
    });

    /* ------------------------------------------------ live network ticker */
    var ticker = document.querySelector("[data-mb-ticker]");
    if (ticker) {
        var elHeight = document.getElementById("mbStatHeight");
        var elSupply = document.getElementById("mbStatSupply");
        var elTx = document.getElementById("mbStatTx");
        var elMempool = document.getElementById("mbStatMempool");
        var pull = function () {
            fetch("/api/blockchain/info")
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (!d || d.status !== "success") return;
                    if (elHeight) elHeight.textContent = d.height;
                    if (elSupply) elSupply.textContent = Number(d.total_money_coins).toLocaleString();
                    if (elTx) elTx.textContent = Number(d.tx_count).toLocaleString();
                    if (elMempool) elMempool.textContent = d.mempool_size;
                })
                .catch(function () { /* silent — marketing band is non-critical */ });
        };
        pull();
        setInterval(pull, 10000);
    }

    /* ------------------------------------------------ scroll reveal */
    var revealEls = document.querySelectorAll(".mb-reveal");
    if (revealEls.length) {
        if ("IntersectionObserver" in window) {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (en) {
                    if (en.isIntersecting) { en.target.classList.add("is-visible"); io.unobserve(en.target); }
                });
            }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
            revealEls.forEach(function (el) { io.observe(el); });
        } else {
            revealEls.forEach(function (el) { el.classList.add("is-visible"); });
        }
    }

    /* ------------------------------------------------ FAQ accordion */
    document.querySelectorAll(".mb-faq-q").forEach(function (q) {
        q.addEventListener("click", function () {
            var item = q.closest(".mb-faq-item");
            var ans = item.querySelector(".mb-faq-a");
            var open = item.classList.toggle("is-open");
            ans.style.maxHeight = open ? ans.scrollHeight + "px" : "0";
        });
    });

    /* ------------------------------------------------ notify capture */
    document.querySelectorAll(".mb-notify-form").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var input = form.querySelector("input[type=email]");
            var email = (input && input.value || "").trim();
            var wrap = form.closest(".mb-notify") || form.parentElement;
            var okEl = wrap.querySelector(".mb-notify-ok");
            if (!email || email.indexOf("@") < 1 || email.indexOf(".") < 0) {
                if (okEl) { okEl.style.color = ""; okEl.textContent = "Please enter a valid email address."; }
                return;
            }
            // Client-side fallback (Railway FS is ephemeral) — remember locally.
            try {
                var saved = JSON.parse(localStorage.getItem("mb_notify") || "[]");
                if (saved.indexOf(email) === -1) { saved.push(email); localStorage.setItem("mb_notify", JSON.stringify(saved)); }
            } catch (err) { /* ignore storage errors */ }

            fetch("/api/notify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: email, source: form.getAttribute("data-source") || "site" })
            }).catch(function () { /* localStorage fallback already applied */ })
              .finally(function () {
                  form.reset();
                  if (okEl) { okEl.style.color = ""; okEl.textContent = "You're on the list. We'll email you when MBITE lists."; }
              });
        });
    });

    /* ------------------------------------------------ footer year */
    var yr = document.getElementById("mbYear");
    if (yr) yr.textContent = new Date().getFullYear();
})();
