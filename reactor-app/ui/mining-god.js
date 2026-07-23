/* ==========================================================================
 * MoonBite — GOD-TIER Cinematic Mining Engine
 * Pure canvas. Zero dependencies. Zero coupling to the mining API/logic:
 * it OBSERVES the existing DOM state (blocks / progress / orb idle-class)
 * that the page's inline script already maintains, and renders a 3D reactor,
 * particle field and live hashrate graph on top. Nothing here starts, stops
 * or talks to mining — it only visualises.
 * ========================================================================== */
(function () {
  "use strict";

  var stage = document.getElementById("godStage");
  if (!stage) return;

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var reactor = document.getElementById("godReactor");
  var particles = document.getElementById("godParticles");
  var spark = document.getElementById("godSpark");
  var rCtx = reactor.getContext("2d");
  var pCtx = particles.getContext("2d");
  var sCtx = spark.getContext("2d");

  // ---- DPI-aware sizing --------------------------------------------------
  var DPR = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0, sW = 0, sH = 0;

  function fit(canvas, ctx) {
    var r = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(r.width * DPR));
    canvas.height = Math.max(1, Math.round(r.height * DPR));
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    return { w: r.width, h: r.height };
  }
  function resize() {
    var a = fit(reactor, rCtx); W = a.w; H = a.h;
    fit(particles, pCtx);
    var s = fit(spark, sCtx); sW = s.w; sH = s.h;
  }
  window.addEventListener("resize", resize);
  resize();

  // The stage starts display:none (revealed only when mining begins), so the
  // canvases would size to 1x1. Re-fit whenever the stage's box changes size
  // — covers the hidden->visible transition and container reflows.
  if (typeof ResizeObserver !== "undefined") {
    var ro = new ResizeObserver(function () { resize(); });
    ro.observe(stage);
  }

  // ---- State read from the live page ------------------------------------
  // intensity 0..1 ramps up while mining, decays when idle.
  var intensity = 0;
  var targetIntensity = 0;
  var hashrate = 0;          // smoothed display value (H/s, synthetic)
  var lastBlocks = 0;
  var burst = 0;             // transient flash when a block lands

  function readState() {
    var orb = document.getElementById("miningOrb");
    var live = orb ? !orb.classList.contains("idle") : false;

    var fillEl = document.getElementById("progressBarFill");
    var pct = 0;
    if (fillEl) { pct = parseFloat(fillEl.style.width) || 0; }

    var blocks = parseInt((document.getElementById("blocksMined") || {}).textContent, 10) || 0;
    if (blocks > lastBlocks) { burst = 1; lastBlocks = blocks; }
    if (blocks < lastBlocks) { lastBlocks = blocks; } // reset between runs

    targetIntensity = live ? 1 : 0;

    // Mirror the real readouts into the cinematic HUD.
    setText("godHeight", (document.getElementById("currentHeight") || {}).textContent || "--");
    setText("godElapsed", (document.getElementById("elapsedTime") || {}).textContent || "0s");
    var total = (document.getElementById("totalBlocks") || {}).textContent || "0";
    setText("godBlocks", blocks + " / " + total);

    // Beam mirrors the real progress width.
    var beam = document.getElementById("godBeamFill");
    if (beam) beam.style.width = pct + "%";
    setText("godPct", Math.round(pct) + "%");

    // State pill text.
    var pill = document.getElementById("godStateText");
    if (pill) pill.textContent = live ? "REACTOR ONLINE" : "STANDBY";
    if (live) stage.classList.add("is-live"); else stage.classList.remove("is-live");
  }
  function setText(id, v) { var el = document.getElementById(id); if (el && el.textContent !== v) el.textContent = v; }

  // ---- Hashrate history (sparkline) -------------------------------------
  var history = new Array(64).fill(0);

  // ---- Particle field ---------------------------------------------------
  var parts = [];
  function seedParticles() {
    parts = [];
    var n = reduce ? 26 : 70;
    for (var i = 0; i < n; i++) {
      parts.push({
        x: Math.random(), y: Math.random(),
        r: 0.6 + Math.random() * 1.8,
        sp: 0.15 + Math.random() * 0.5,
        drift: (Math.random() - 0.5) * 0.25,
        hue: Math.random()
      });
    }
  }
  seedParticles();

  function drawParticles() {
    pCtx.clearRect(0, 0, W, H);
    var cx = W / 2, cy = H * 0.46;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      // Rise + slight swirl toward the core when live.
      p.y -= (p.sp * (0.4 + intensity)) / H;
      p.x += (p.drift * (0.3 + intensity)) / W;
      if (p.y < -0.05) { p.y = 1.05; p.x = Math.random(); }
      var px = p.x * W, py = p.y * H;
      // Pull toward the core with intensity for a "vortex" feel.
      px += (cx - px) * 0.06 * intensity;
      var col = p.hue < 0.5
        ? "rgba(124,92,255," : (p.hue < 0.8 ? "rgba(52,211,255," : "rgba(34,229,168,");
      var a = (0.15 + 0.55 * intensity) * (0.6 + 0.4 * Math.sin((py + i) * 0.05));
      pCtx.beginPath();
      pCtx.fillStyle = col + a.toFixed(3) + ")";
      pCtx.arc(px, py, p.r * (0.8 + intensity * 0.9), 0, Math.PI * 2);
      pCtx.fill();
    }
  }

  // ---- Pseudo-3D reactor (icosahedron wireframe + orbiting nodes) --------
  var t = 1.618033988749895;
  var verts = [
    [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
    [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
    [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]
  ];
  var edges = [
    [0,1],[0,5],[0,7],[0,10],[0,11],[1,5],[1,7],[1,8],[1,9],
    [2,3],[2,4],[2,6],[2,10],[2,11],[3,4],[3,6],[3,8],[3,9],
    [4,5],[4,9],[4,11],[5,9],[5,11],[6,7],[6,8],[6,10],
    [7,8],[7,10],[8,9],[10,11]
  ];
  var ang = 0;

  function rot(p, ax, ay) {
    var cosy = Math.cos(ay), siny = Math.sin(ay);
    var cosx = Math.cos(ax), sinx = Math.sin(ax);
    var x = p[0] * cosy - p[2] * siny;
    var z = p[0] * siny + p[2] * cosy;
    var y = p[1] * cosx - z * sinx;
    z = p[1] * sinx + z * cosx;
    return [x, y, z];
  }

  function drawReactor(dt) {
    rCtx.clearRect(0, 0, W, H);
    var cx = W / 2, cy = H * 0.46;
    var baseR = Math.min(W, H) * 0.20;
    var R = baseR * (1 + 0.06 * Math.sin(ang * 2) + burst * 0.18);
    ang += dt * (0.15 + intensity * 0.9);

    // Projected vertices.
    var proj = [];
    for (var i = 0; i < verts.length; i++) {
      var v = rot(verts[i], ang * 0.6, ang);
      var scale = 220 / (220 + v[2] * 40);
      proj.push({
        x: cx + v[0] * R * scale,
        y: cy + v[1] * R * scale,
        z: v[2], s: scale
      });
    }

    // Glow core.
    var g = rCtx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.7);
    var coreA = 0.35 + intensity * 0.4 + burst * 0.3;
    g.addColorStop(0, "rgba(180,210,255," + Math.min(0.9, coreA) + ")");
    g.addColorStop(0.4, "rgba(124,92,255," + (0.25 + intensity * 0.3) + ")");
    g.addColorStop(1, "rgba(124,92,255,0)");
    rCtx.fillStyle = g;
    rCtx.beginPath();
    rCtx.arc(cx, cy, R * 1.7, 0, Math.PI * 2);
    rCtx.fill();

    // Edges (depth-shaded).
    rCtx.lineWidth = 1.2;
    for (var e = 0; e < edges.length; e++) {
      var a = proj[edges[e][0]], b = proj[edges[e][1]];
      var depth = (a.z + b.z) / 2;
      var alpha = 0.25 + (depth + 2) / 4 * (0.55 + intensity * 0.35);
      rCtx.strokeStyle = depth > 0
        ? "rgba(52,211,255," + alpha.toFixed(3) + ")"
        : "rgba(124,92,255," + (alpha * 0.7).toFixed(3) + ")";
      rCtx.beginPath();
      rCtx.moveTo(a.x, a.y);
      rCtx.lineTo(b.x, b.y);
      rCtx.stroke();
    }

    // Vertex nodes.
    for (var j = 0; j < proj.length; j++) {
      var pt = proj[j];
      var nr = (1.6 + pt.s * 1.6) * (1 + intensity * 0.5);
      rCtx.beginPath();
      rCtx.fillStyle = pt.z > 0 ? "#8ff0ff" : "#b9a4ff";
      rCtx.globalAlpha = 0.5 + pt.s * 0.5;
      rCtx.arc(pt.x, pt.y, nr, 0, Math.PI * 2);
      rCtx.fill();
    }
    rCtx.globalAlpha = 1;

    // Two orbiting energy rings.
    for (var k = 0; k < 2; k++) {
      var tilt = k === 0 ? 0.5 : -0.85;
      rCtx.save();
      rCtx.translate(cx, cy);
      rCtx.scale(1, 0.34 + 0.12 * Math.sin(ang + k));
      rCtx.rotate(ang * (k ? -0.8 : 1.1) + tilt);
      rCtx.beginPath();
      rCtx.strokeStyle = k === 0
        ? "rgba(34,229,168," + (0.35 + intensity * 0.4) + ")"
        : "rgba(255,92,200," + (0.30 + intensity * 0.4) + ")";
      rCtx.lineWidth = 1.6;
      rCtx.arc(0, 0, R * 1.55, 0, Math.PI * 2);
      rCtx.stroke();
      // A traveling spark on the ring.
      var sx = Math.cos(ang * 3 + k) * R * 1.55;
      var sy = Math.sin(ang * 3 + k) * R * 1.55;
      rCtx.beginPath();
      rCtx.fillStyle = k === 0 ? "#22e5a8" : "#ff5cc8";
      rCtx.arc(sx, sy, 3 + intensity * 2, 0, Math.PI * 2);
      rCtx.fill();
      rCtx.restore();
    }
  }

  // ---- Sparkline --------------------------------------------------------
  function drawSpark() {
    sCtx.clearRect(0, 0, sW, sH);
    var max = 1;
    for (var i = 0; i < history.length; i++) if (history[i] > max) max = history[i];
    // baseline
    sCtx.strokeStyle = "rgba(52,211,255,0.15)";
    sCtx.lineWidth = 1;
    sCtx.beginPath(); sCtx.moveTo(0, sH - 0.5); sCtx.lineTo(sW, sH - 0.5); sCtx.stroke();
    // area + line
    var grd = sCtx.createLinearGradient(0, 0, 0, sH);
    grd.addColorStop(0, "rgba(52,211,255,0.45)");
    grd.addColorStop(1, "rgba(124,92,255,0.02)");
    sCtx.beginPath();
    for (var j = 0; j < history.length; j++) {
      var x = (j / (history.length - 1)) * sW;
      var y = sH - (history[j] / max) * (sH - 4) - 2;
      if (j === 0) sCtx.moveTo(x, y); else sCtx.lineTo(x, y);
    }
    sCtx.lineTo(sW, sH); sCtx.lineTo(0, sH); sCtx.closePath();
    sCtx.fillStyle = grd; sCtx.fill();

    sCtx.beginPath();
    for (var k = 0; k < history.length; k++) {
      var x2 = (k / (history.length - 1)) * sW;
      var y2 = sH - (history[k] / max) * (sH - 4) - 2;
      if (k === 0) sCtx.moveTo(x2, y2); else sCtx.lineTo(x2, y2);
    }
    sCtx.strokeStyle = "#34d3ff";
    sCtx.lineWidth = 1.5;
    sCtx.stroke();
  }

  // ---- Hashrate readout formatting --------------------------------------
  function fmtRate(v) {
    if (v >= 1e6) return (v / 1e6).toFixed(2) + " MH/s";
    if (v >= 1e3) return (v / 1e3).toFixed(2) + " kH/s";
    return Math.round(v) + " H/s";
  }

  // ---- Main loop --------------------------------------------------------
  var last = performance.now();
  var sparkAccum = 0;

  function frame(now) {
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;

    // Safety: if the reactor canvas box no longer matches its backing store
    // (e.g. it was 1x1 while hidden), re-fit before drawing.
    var rr = reactor.getBoundingClientRect();
    if (Math.abs(rr.width - W) > 1 || Math.abs(rr.height - H) > 1) { resize(); }

    readState();

    // Smooth intensity + decay burst.
    intensity += (targetIntensity - intensity) * Math.min(1, dt * 3);
    burst *= Math.pow(0.02, dt); // fast decay

    // Synthetic-but-lively hashrate: scales with intensity, jitters, spikes on burst.
    var target = intensity * (85000 + Math.sin(now * 0.002) * 12000) + burst * 40000;
    hashrate += (target - hashrate) * Math.min(1, dt * 4);
    var jitter = hashrate * (1 + (Math.random() - 0.5) * 0.06 * intensity);
    var rateEl = document.getElementById("godHashrate");
    if (rateEl) rateEl.textContent = intensity > 0.02 ? fmtRate(jitter) : "0 H/s";

    // Push into history ~15x/sec.
    sparkAccum += dt;
    if (sparkAccum > 0.066) {
      history.push(jitter);
      history.shift();
      sparkAccum = 0;
      drawSpark();
    }

    if (reduce) {
      // Static-ish: draw once-ish but cheaply.
      drawReactor(dt * 0.15);
      drawParticles();
    } else {
      drawReactor(dt);
      drawParticles();
    }

    raf = requestAnimationFrame(frame);
  }

  var raf = requestAnimationFrame(frame);

  // Pause when tab hidden to save cycles.
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { cancelAnimationFrame(raf); }
    else { last = performance.now(); raf = requestAnimationFrame(frame); }
  });
})();
