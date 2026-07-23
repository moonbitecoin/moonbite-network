/* ============================================================================
   MoonBite CINEMATIC FILM — the whole home page is one continuous, scroll-driven
   shot. A sticky stage holds a persistent starfield + a flying moon while eight
   "chapters" cross-fade over it as you scroll. No stacked sections.

   Self-contained IIFE. Loaded only on / via home.html scripts_extra (defer).
   - No JS / reduced motion  -> normal vertical flow, all chapters visible.
   - Full motion             -> adds .is-film, drives the flight from scroll.
   ========================================================================== */
(function () {
    "use strict";

    var reduce = window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var film = document.getElementById("film");
    var chapters = film ? film.querySelectorAll(".chapter") : [];
    var N = chapters.length || 1;

    /* ---------------------------------------------------------- STARFIELD */
    var canvas = document.getElementById("cineStars");
    if (canvas && canvas.getContext) {
        var ctx = canvas.getContext("2d");
        var stars = [];
        var shooters = [];
        var w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
        var raf = null;
        var mx = 0, my = 0, tmx = 0, tmy = 0;
        var flight = 0; // 0..1 scroll progress, fed by the film engine below

        function resize() {
            w = canvas.clientWidth;
            h = canvas.clientHeight;
            canvas.width = Math.floor(w * dpr);
            canvas.height = Math.floor(h * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            buildStars();
        }

        function buildStars() {
            var count = Math.min(240, Math.floor((w * h) / 6200));
            stars = [];
            for (var i = 0; i < count; i++) {
                var layer = Math.random();
                stars.push({
                    x: Math.random() * w,
                    y: Math.random() * h,
                    r: layer * 1.7 + 0.3,
                    z: 0.25 + layer * 0.85,           // parallax + flight depth
                    tw: Math.random() * Math.PI * 2,
                    tws: 0.008 + Math.random() * 0.03,
                    hue: Math.random() < 0.18 ? "52,211,255"
                        : (Math.random() < 0.2 ? "124,92,255" : "230,235,255")
                });
            }
        }

        function spawnShooter() {
            if (reduce) return;
            var fromLeft = Math.random() < 0.5;
            shooters.push({
                x: fromLeft ? -40 : w + 40,
                y: Math.random() * h * 0.5,
                vx: (fromLeft ? 1 : -1) * (6 + Math.random() * 5),
                vy: 2 + Math.random() * 2.5,
                life: 0,
                max: 60 + Math.random() * 30
            });
        }

        function frame() {
            ctx.clearRect(0, 0, w, h);
            mx += (tmx - mx) * 0.05;
            my += (tmy - my) * 0.05;

            var cx = w / 2, cy = h * 0.5;
            // As we "fly", stars drift outward from the centre + speed up twinkle.
            var push = flight * 1.0;

            for (var i = 0; i < stars.length; i++) {
                var s = stars[i];
                s.tw += s.tws;
                var a = 0.35 + Math.abs(Math.sin(s.tw)) * 0.65;
                var ox = (s.x - cx) * push * s.z * 0.55;
                var oy = (s.y - cy) * push * s.z * 0.55;
                var px = s.x + ox + mx * s.z * 22;
                var py = s.y + oy + my * s.z * 22;
                ctx.beginPath();
                ctx.arc(px, py, s.r, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(" + s.hue + "," + a.toFixed(3) + ")";
                ctx.fill();
                if (s.r > 1.2) {
                    ctx.beginPath();
                    ctx.arc(px, py, s.r * 2.6, 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(" + s.hue + "," + (a * 0.12).toFixed(3) + ")";
                    ctx.fill();
                }
            }

            for (var j = shooters.length - 1; j >= 0; j--) {
                var sh = shooters[j];
                sh.life++;
                sh.x += sh.vx;
                sh.y += sh.vy;
                var t = 1 - sh.life / sh.max;
                if (t <= 0) { shooters.splice(j, 1); continue; }
                var tailX = sh.x - sh.vx * 6;
                var tailY = sh.y - sh.vy * 6;
                var grad = ctx.createLinearGradient(sh.x, sh.y, tailX, tailY);
                grad.addColorStop(0, "rgba(255,255,255," + (0.9 * t).toFixed(3) + ")");
                grad.addColorStop(1, "rgba(124,92,255,0)");
                ctx.strokeStyle = grad;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(sh.x, sh.y);
                ctx.lineTo(tailX, tailY);
                ctx.stroke();
            }

            raf = requestAnimationFrame(frame);
        }

        window.addEventListener("resize", resize, { passive: true });
        resize();

        if (reduce) {
            for (var k = 0; k < stars.length; k++) {
                var st = stars[k];
                ctx.beginPath();
                ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(" + st.hue + ",0.8)";
                ctx.fill();
            }
        } else {
            raf = requestAnimationFrame(frame);
            setInterval(spawnShooter, 4200);
            document.addEventListener("visibilitychange", function () {
                if (document.hidden) { if (raf) cancelAnimationFrame(raf); raf = null; }
                else if (!raf) { raf = requestAnimationFrame(frame); }
            });
            window.addEventListener("mousemove", function (e) {
                tmx = (e.clientX / window.innerWidth) - 0.5;
                tmy = (e.clientY / window.innerHeight) - 0.5;
            }, { passive: true });
        }

        // Expose so the film engine can feed scroll progress into the starfield.
        window.__cineSetFlight = function (p) { flight = p; };
    }

    /* -------------------------------------------------------- FILM ENGINE */
    var moon = film ? film.querySelector(".film-moonwrap") : null;
    var cue = film ? film.querySelector(".film-cue") : null;
    var progFill = document.querySelector(".cine-progress > span");
    var progMoon = document.querySelector(".cine-progress-moon");
    var curve = document.querySelector(".cine-curve-line");
    var curveLen = 0;
    if (curve && curve.getTotalLength) {
        curveLen = curve.getTotalLength();
        curve.style.strokeDasharray = curveLen;
    }

    function setProgressBar(p) {
        var pct = (p * 100).toFixed(2) + "%";
        if (progFill) progFill.style.width = pct;
        if (progMoon) progMoon.style.left = pct;
    }

    // The sticky cross-fade film gives each chapter one full viewport. That only
    // works when the viewport is big enough for a chapter's multi-column layout
    // to fit; on phones the columns stack and would clip inside the pinned stage,
    // so those get the clean, fully-readable vertical fallback instead.
    var roomy = window.innerWidth >= 900 && window.innerHeight >= 600;

    if (!film || reduce || N < 2 || !roomy) {
        // Fallback: normal flow. Reveal everything, draw the curve fully.
        for (var f = 0; f < chapters.length; f++) chapters[f].classList.add("is-active");
        if (curve) curve.style.strokeDashoffset = 0;
        var chart0 = document.querySelector(".cine-chart");
        if (chart0) chart0.classList.add("is-drawn");
        setProgressBar(0);
    } else {
        film.classList.add("is-film");
        // Give the flight some room: one screen per chapter, plus a little tail.
        var track = Math.round(N * 100 + 20);
        film.style.setProperty("--film-h", track + "vh");

        var ticking = false;
        var chart = document.querySelector(".cine-chart");

        function render() {
            var rect = film.getBoundingClientRect();
            var total = film.offsetHeight - window.innerHeight;
            if (total <= 0) total = 1;
            var scrolled = -rect.top;
            scrolled = scrolled < 0 ? 0 : (scrolled > total ? total : scrolled);
            var p = scrolled / total;

            // Feed the starfield so stars stream past as we fly.
            if (window.__cineSetFlight) window.__cineSetFlight(p);

            // Persistent moon flies across + shrinks + slowly rotates.
            if (moon) {
                var tx = (-p * 12).toFixed(2) + "vw";
                var ty = (-p * 16).toFixed(2) + "vh";
                var sc = (1.15 - p * 0.8).toFixed(3);
                var rot = (p * 40).toFixed(2) + "deg";
                moon.style.transform =
                    "translate3d(" + tx + "," + ty + ",0) scale(" + sc + ") rotate(" + rot + ")";
            }

            // Cross-fade the chapters. Chapter i peaks at pos == i, so the first
            // chapter is fully lit at the very top (p=0) and the last at p=1.
            var pos = p * (N - 1);
            var activeIdx = 0, activeDist = 1e9;
            for (var i = 0; i < N; i++) {
                var local = pos - i;          // 0 at this chapter's peak
                var ad = Math.abs(local);
                var opacity = 1 - ad;         // linear cross-fade, sums to ~1
                opacity = opacity < 0 ? 0 : (opacity > 1 ? 1 : opacity);
                var translateY = (local * -60).toFixed(1);
                var scale = (1 - ad * 0.10).toFixed(3);
                var ch = chapters[i];
                ch.style.opacity = opacity.toFixed(3);
                ch.style.transform =
                    "translate3d(0," + translateY + "px,0) scale(" + scale + ")";
                if (ad < activeDist) { activeDist = ad; activeIdx = i; }
            }
            for (var a = 0; a < N; a++) {
                if (a === activeIdx) chapters[a].classList.add("is-active");
                else chapters[a].classList.remove("is-active");
            }

            // Emission curve draws while its chapter (index 5) is on screen.
            if (curve && curveLen) {
                var dp = 1 - Math.min(Math.abs(pos - 5) * 1.4, 1);
                dp = dp < 0 ? 0 : dp;
                curve.style.strokeDashoffset = (curveLen * (1 - dp)).toFixed(1);
                if (chart && dp > 0.06) chart.classList.add("is-drawn");
            }

            // Fade the scroll cue away after we leave the first chapter.
            if (cue) cue.style.opacity = p > 0.04 ? "0" : "1";

            setProgressBar(p);
            ticking = false;
        }

        window.addEventListener("scroll", function () {
            if (!ticking) { ticking = true; requestAnimationFrame(render); }
        }, { passive: true });
        window.addEventListener("resize", function () {
            if (!ticking) { ticking = true; requestAnimationFrame(render); }
        }, { passive: true });
        render();
    }
})();
