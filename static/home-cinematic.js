/* ============================================================================
   MoonBite cinematic homepage — starfield, parallax, kinetic headline.
   Self-contained IIFE. Loaded only on / via home.html scripts_extra (defer).
   Respects prefers-reduced-motion and degrades gracefully.
   ========================================================================== */
(function () {
    "use strict";

    window.__cineHomeVersion = 3;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* ---------------------------------------------------- STARFIELD */
    var canvas = document.getElementById("cineStars");
    if (canvas && canvas.getContext) {
        var ctx = canvas.getContext("2d");
        var stars = [];
        var shooters = [];
        var w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
        var raf = null;

        function resize() {
            w = canvas.clientWidth;
            h = canvas.clientHeight;
            canvas.width = Math.floor(w * dpr);
            canvas.height = Math.floor(h * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            buildStars();
        }

        function buildStars() {
            var count = Math.min(220, Math.floor((w * h) / 6500));
            stars = [];
            for (var i = 0; i < count; i++) {
                var layer = Math.random();
                stars.push({
                    x: Math.random() * w,
                    y: Math.random() * h,
                    r: layer * 1.6 + 0.3,
                    z: 0.25 + layer * 0.75,          // parallax depth
                    tw: Math.random() * Math.PI * 2,  // twinkle phase
                    tws: 0.008 + Math.random() * 0.03,
                    hue: Math.random() < 0.18 ? "52,211,255" : (Math.random() < 0.2 ? "124,92,255" : "230,235,255")
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

        var mx = 0, my = 0, tmx = 0, tmy = 0;

        function frame() {
            ctx.clearRect(0, 0, w, h);
            mx += (tmx - mx) * 0.05;
            my += (tmy - my) * 0.05;

            for (var i = 0; i < stars.length; i++) {
                var s = stars[i];
                s.tw += s.tws;
                var a = 0.35 + Math.abs(Math.sin(s.tw)) * 0.65;
                var px = s.x + mx * s.z * 22;
                var py = s.y + my * s.z * 22;
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
            // Paint one static frame, no animation loop.
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

            // Pause when tab hidden (save cycles)
            document.addEventListener("visibilitychange", function () {
                if (document.hidden) { if (raf) cancelAnimationFrame(raf); raf = null; }
                else if (!raf) { raf = requestAnimationFrame(frame); }
            });

            /* ------------------------------------------ MOUSE PARALLAX */
            var scene = document.querySelector(".cine-scene");
            var orbit = document.querySelector(".cine-orbit-wrap");
            window.addEventListener("mousemove", function (e) {
                var nx = (e.clientX / window.innerWidth) - 0.5;
                var ny = (e.clientY / window.innerHeight) - 0.5;
                tmx = nx; tmy = ny;
                if (orbit) orbit.style.transform = "translate3d(" + (nx * 26) + "px," + (ny * 20) + "px,0)";
                if (scene) scene.style.transform = "translate3d(" + (nx * -10) + "px," + (ny * -8) + "px,0)";
            }, { passive: true });
        }
    }

    /* -------------------------------------------- KINETIC HEADLINE */
    var title = document.querySelector(".cine-title");
    if (title && !title.dataset.split) {
        title.dataset.split = "1";
        var walk = function (node) {
            var kids = Array.prototype.slice.call(node.childNodes);
            kids.forEach(function (child) {
                if (child.nodeType === 3) {
                    var frag = document.createDocumentFragment();
                    child.textContent.split(/(\s+)/).forEach(function (part) {
                        if (part.trim() === "") { frag.appendChild(document.createTextNode(part)); return; }
                        var span = document.createElement("span");
                        span.className = "cine-word";
                        span.textContent = part;
                        frag.appendChild(span);
                    });
                    node.replaceChild(frag, child);
                } else if (child.nodeType === 1) {
                    // keep gradient wrappers, split their text too
                    walk(child);
                }
            });
        };
        walk(title);
        var words = title.querySelectorAll(".cine-word");
        words.forEach(function (word, i) {
            word.style.animationDelay = (0.15 + i * 0.08) + "s";
        });
    }

    /* ------------------------------------------- STAT COUNT-UP PODS */
    // Enhance the ticker values with an animated count-up whenever they change.
    function countUp(el, target) {
        if (reduce) { el.textContent = target.toLocaleString(); return; }
        var start = 0, dur = 900, t0 = performance.now();
        function step(now) {
            var p = Math.min((now - t0) / dur, 1);
            var eased = 1 - Math.pow(1 - p, 3);
            el.textContent = Math.floor(start + (target - start) * eased).toLocaleString();
            if (p < 1) requestAnimationFrame(step);
            else el.textContent = target.toLocaleString();
        }
        requestAnimationFrame(step);
    }

    var podMap = [
        ["cinePodHeight", "mbStatHeight"],
        ["cinePodSupply", "mbStatSupply"],
        ["cinePodTx", "mbStatTx"],
        ["cinePodMempool", "mbStatMempool"]
    ];
    // Poll the hidden ticker values (site.js fills them) and mirror into pods.
    var lastVals = {};
    setInterval(function () {
        podMap.forEach(function (pair) {
            var pod = document.getElementById(pair[0]);
            var src = document.getElementById(pair[1]);
            if (!pod || !src) return;
            var raw = (src.textContent || "").replace(/[^0-9]/g, "");
            if (raw === "" ) return;
            var n = parseInt(raw, 10);
            if (lastVals[pair[0]] !== n) {
                lastVals[pair[0]] = n;
                countUp(pod, n);
            }
        });
    }, 1000);

    /* -------------------------------------- LUNAR SCROLL PROGRESS */
    var progFill = document.querySelector(".cine-progress > span");
    var progMoon = document.querySelector(".cine-progress-moon");
    if (progFill) {
        function updateProgress() {
            var doc = document.documentElement;
            var max = (doc.scrollHeight - doc.clientHeight) || 1;
            var y = window.scrollY || window.pageYOffset || doc.scrollTop || 0;
            var p = Math.min(Math.max(y / max, 0), 1);
            var pct = (p * 100).toFixed(2) + "%";
            progFill.style.width = pct;
            if (progMoon) progMoon.style.left = pct;
        }
        window.addEventListener("scroll", updateProgress, { passive: true });
        window.addEventListener("resize", updateProgress, { passive: true });
        updateProgress();
    }

    /* --------------------------------- EMISSION CURVE: DRAW ON SCROLL */
    var chart = document.querySelector(".cine-chart");
    var curve = document.querySelector(".cine-curve-line");
    if (chart && curve && curve.getTotalLength) {
        var len = curve.getTotalLength();
        curve.style.strokeDasharray = len;
        if (reduce) {
            curve.style.strokeDashoffset = 0;
            chart.classList.add("is-drawn");
        } else {
            curve.style.strokeDashoffset = len;
            var drawn = false;
            var drawTick = false;
            function drawCurve() {
                var rect = chart.getBoundingClientRect();
                var vh = window.innerHeight || 800;
                // progress: 0 when chart top hits 85% of viewport, 1 when it reaches 25%
                var start = vh * 0.85, end = vh * 0.25;
                var p = (start - rect.top) / (start - end);
                p = Math.min(Math.max(p, 0), 1);
                curve.style.strokeDashoffset = (len * (1 - p)).toFixed(1);
                if (p > 0.06) chart.classList.add("is-drawn");
                drawTick = false;
            }
            window.addEventListener("scroll", function () {
                if (!drawTick) { drawTick = true; requestAnimationFrame(drawCurve); }
            }, { passive: true });
            window.addEventListener("resize", drawCurve, { passive: true });
            drawCurve();
        }
    }

    /* ------------------------------------------------ SCROLL REVEAL */
    var revealEls = document.querySelectorAll(".cine-reveal");
    if ("IntersectionObserver" in window && revealEls.length) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                if (en.isIntersecting) { en.target.classList.add("is-visible"); io.unobserve(en.target); }
            });
        }, { threshold: 0.14 });
        revealEls.forEach(function (el) { io.observe(el); });
    } else {
        revealEls.forEach(function (el) { el.classList.add("is-visible"); });
    }

    /* ------------------------ SCENE CHOREOGRAPHY (whole-page cinema) */
    // Feed each section a live --enter (0 → 1) tied to its viewport position,
    // so the whole page reads as one continuous flight through space rather
    // than a stack of static slabs. CSS turns --enter into drift + scale.
    var sceneEls = document.querySelectorAll(".cine-scene-block");
    if (sceneEls.length) {
        if (reduce) {
            for (var s = 0; s < sceneEls.length; s++) {
                sceneEls[s].style.setProperty("--enter", "1");
            }
        } else {
            var sceneTick = false;
            var choreograph = function () {
                var vh = window.innerHeight || 800;
                var start = vh * 0.96, end = vh * 0.60;
                for (var i = 0; i < sceneEls.length; i++) {
                    var rect = sceneEls[i].getBoundingClientRect();
                    var p = (start - rect.top) / (start - end);
                    p = p < 0 ? 0 : (p > 1 ? 1 : p);
                    p = 1 - Math.pow(1 - p, 3); // ease-out for a soft landing
                    sceneEls[i].style.setProperty("--enter", p.toFixed(3));
                }
                sceneTick = false;
            };
            window.addEventListener("scroll", function () {
                if (!sceneTick) { sceneTick = true; requestAnimationFrame(choreograph); }
            }, { passive: true });
            window.addEventListener("resize", choreograph, { passive: true });
            choreograph();
        }
    }
})();
