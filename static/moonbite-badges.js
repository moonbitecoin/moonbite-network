/* MoonBite Badges — first-block celebration + earned-badge system.
 *
 * Self-contained: no libraries, no network calls. State lives in
 * localStorage under one key, scoped per mining address so a shared
 * machine can hold several miners' histories.
 *
 * Public API (all safe to call even if the DOM shelf is absent):
 *   MoonBiteBadges.recordBlocks(sessionBlocks, chainHeight, address)
 *     — call from the mining status poll; detects the first-ever block
 *       (full-screen celebration) and awards later badges with a toast.
 *   MoonBiteBadges.renderShelf(elId, address) — paint earned badges.
 */
(function () {
  'use strict';

  var STORE_KEY = 'mb_miner_profiles';

  /* The block reward is consensus, not a constant to hardcode here: it halves
     on schedule, so the ceremony asks the server and degrades to a neutral
     label if the call fails. */
  var REWARD_LABEL = 'MBITE';
  try {
    fetch('/api/consensus').then(function (r) { return r.json(); }).then(function (c) {
      if (c && c.current_reward_coins) REWARD_LABEL = '+' + c.current_reward_coins + ' MBITE';
    }).catch(function () {});
  } catch (e) {}

  /* Badges are earned by verifiable local events only. Height tiers are
   * judged by the chain height when the miner's FIRST block landed —
   * being early is the one thing latecomers cannot copy. */
  var BADGES = [
    { id: 'first_bite',  icon: '🌑', name: 'First Bite',      desc: 'Mined your first block',                  test: function (p) { return p.totalBlocks >= 1; } },
    { id: 'genesis',     icon: '🌟', name: 'Genesis Miner',   desc: 'First block before height 10,000',        test: function (p) { return p.totalBlocks >= 1 && p.firstHeight < 10000; } },
    { id: 'pioneer',     icon: '🚀', name: 'Pioneer',         desc: 'First block before height 100,000',       test: function (p) { return p.totalBlocks >= 1 && p.firstHeight < 100000; } },
    { id: 'pre_halving', icon: '⏳', name: 'Pre-Halving',     desc: 'First block before the 1,000,000 halving', test: function (p) { return p.totalBlocks >= 1 && p.firstHeight < 1000000; } },
    { id: 'ten',         icon: '⛏️', name: 'Ten Bites',       desc: 'Mined 10 blocks',                         test: function (p) { return p.totalBlocks >= 10; } },
    { id: 'hundred',     icon: '💯', name: 'Hundred Bites',   desc: 'Mined 100 blocks',                        test: function (p) { return p.totalBlocks >= 100; } },
    { id: 'week_streak', icon: '🔥', name: 'Seven Moons',     desc: 'Mined on 7 different days',               test: function (p) { return p.miningDays.length >= 7; } }
  ];

  function loadAll() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function saveAll(all) { localStorage.setItem(STORE_KEY, JSON.stringify(all)); }

  function profileFor(address) {
    var all = loadAll();
    if (!all[address]) {
      all[address] = { totalBlocks: 0, sessionBase: 0, firstHeight: null,
                       firstDate: null, miningDays: [], badges: [] };
      saveAll(all);
    }
    return all[address];
  }
  function saveProfile(address, p) {
    var all = loadAll(); all[address] = p; saveAll(all);
  }

  /* ---------------------------------------------------------------- record */
  var lastSession = 0;

  function recordBlocks(sessionBlocks, chainHeight, address) {
    if (!address || typeof sessionBlocks !== 'number') return;
    var p = profileFor(address);

    // Session counter resets each run; only count increases.
    var delta = sessionBlocks - lastSession;
    if (sessionBlocks < lastSession) { delta = sessionBlocks; } // new session
    lastSession = sessionBlocks;
    if (delta <= 0) return;

    var hadNoBlocks = p.totalBlocks === 0;
    p.totalBlocks += delta;
    if (p.firstHeight === null) {
      p.firstHeight = Math.max(0, (chainHeight || 0) - delta + 1);
      p.firstDate = new Date().toISOString();
    }
    var today = new Date().toISOString().slice(0, 10);
    if (p.miningDays.indexOf(today) === -1) p.miningDays.push(today);

    // Evaluate badges; collect the newly earned.
    var fresh = [];
    BADGES.forEach(function (b) {
      if (p.badges.indexOf(b.id) === -1 && b.test(p)) {
        p.badges.push(b.id); fresh.push(b);
      }
    });
    saveProfile(address, p);

    if (hadNoBlocks) {
      /* Hand the block to /wall so it can offer a claim form there, rather
         than prompting for a handle mid-ceremony. */
      try {
        localStorage.setItem('mb_last_block', JSON.stringify({
          address: address, height: p.firstHeight, date: p.firstDate
        }));
      } catch (e) {}
      celebrateFirstBlock(p, address, fresh);
    } else {
      fresh.forEach(function (b, i) {
        setTimeout(function () { toast(b.icon + ' Badge earned: ' + b.name); }, i * 2200);
      });
    }
    renderShelf('mbBadgeShelf', address);
  }

  /* ----------------------------------------------------------------- shelf */
  function renderShelf(elId, address) {
    var el = document.getElementById(elId);
    if (!el) return;
    var p = address ? profileFor(address) : null;
    var earned = p ? p.badges : [];
    el.innerHTML = BADGES.map(function (b) {
      var got = earned.indexOf(b.id) !== -1;
      return '<div class="mb-badge' + (got ? ' earned' : '') + '" title="' +
        b.name + ' — ' + b.desc + '">' +
        '<span class="mb-badge-icon">' + b.icon + '</span>' +
        '<span class="mb-badge-name">' + b.name + '</span></div>';
    }).join('');
  }

  /* ----------------------------------------------------------------- toast */
  function toast(msg) {
    var t = document.createElement('div');
    t.className = 'mb-badge-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('show'); });
    setTimeout(function () {
      t.classList.remove('show');
      setTimeout(function () { t.remove(); }, 400);
    }, 3500);
  }

  /* ------------------------------------------------- first-block ceremony */
  function celebrateFirstBlock(p, address, freshBadges) {
    /* Doc 18: first and last six always visible. */
    var short = address.length > 14
      ? address.slice(0, 6) + '…' + address.slice(-6) : address;
    var dateStr = new Date(p.firstDate).toUTCString().slice(5, 16);

    var ov = document.createElement('div');
    ov.className = 'mb-first-block-overlay';
    ov.innerHTML =
      '<canvas class="mb-confetti"></canvas>' +
      '<div class="mb-first-block-card">' +
        '<div class="mb-fb-kicker">FIRST BLOCK FOUND</div>' +
        '<div class="mb-fb-amount">' + REWARD_LABEL + '</div>' +
        '<div class="mb-fb-line">Block #' + p.firstHeight.toLocaleString('en-US') +
          ' · ' + dateStr + '</div>' +
        '<div class="mb-fb-line mb-fb-addr">' + short + '</div>' +
        '<div class="mb-fb-badges">' + freshBadges.map(function (b) {
          return '<span class="mb-fb-badge">' + b.icon + ' ' + b.name + '</span>';
        }).join('') + '</div>' +
        '<div class="mb-fb-quote">Proof-of-work, not proof-of-purchase. You earned this.</div>' +
        '<div class="mb-fb-actions">' +
          '<button class="mb-fb-btn" id="mbFbCert">🖼️ Save certificate</button>' +
          '<a class="mb-fb-btn" href="/wall?claim=1" style="text-decoration:none;">🏛 Put it on the Wall</a>' +
          '<button class="mb-fb-btn ghost" id="mbFbClose">Keep mining →</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(ov);

    confetti(ov.querySelector('.mb-confetti'));
    ov.querySelector('#mbFbClose').addEventListener('click', function () { ov.remove(); });
    ov.querySelector('#mbFbCert').addEventListener('click', function () {
      certificate(p, short, freshBadges);
    });
  }

  function confetti(canvas) {
    canvas.width = window.innerWidth; canvas.height = window.innerHeight;
    var g = canvas.getContext('2d');
    var colors = ['#D9A441', '#B8863B', '#2E9E6B', '#FFFFFF'];
    var bits = [];
    for (var i = 0; i < 160; i++) {
      bits.push({ x: Math.random() * canvas.width, y: -20 - Math.random() * canvas.height * 0.5,
                  s: 4 + Math.random() * 6, v: 2 + Math.random() * 4,
                  w: Math.random() * 2 - 1, c: colors[i % colors.length],
                  r: Math.random() * Math.PI });
    }
    var frames = 0;
    (function tick() {
      g.clearRect(0, 0, canvas.width, canvas.height);
      bits.forEach(function (b) {
        b.y += b.v; b.x += b.w; b.r += 0.08;
        g.save(); g.translate(b.x, b.y); g.rotate(b.r);
        g.fillStyle = b.c; g.fillRect(-b.s / 2, -b.s / 2, b.s, b.s * 0.6);
        g.restore();
      });
      if (++frames < 420 && canvas.isConnected) requestAnimationFrame(tick);
    })();
  }

  function certificate(p, shortAddr, freshBadges) {
    var cv = document.createElement('canvas');
    cv.width = 1080; cv.height = 1080;
    var g = cv.getContext('2d');
    var grad = g.createLinearGradient(0, 0, 0, 1080);
    grad.addColorStop(0, '#0B0D12'); grad.addColorStop(1, '#1A1E27');
    g.fillStyle = grad; g.fillRect(0, 0, 1080, 1080);
    g.strokeStyle = 'rgba(217,164,65,0.5)'; g.lineWidth = 6;
    g.strokeRect(40, 40, 1000, 1000);
    // Bitten moon
    g.beginPath(); g.arc(540, 280, 130, 0, Math.PI * 2); g.fillStyle = '#D9A441'; g.fill();
    g.beginPath(); g.arc(625, 235, 95, 0, Math.PI * 2); g.fillStyle = '#0B0D12'; g.fill();
    g.textAlign = 'center';
    g.fillStyle = 'rgba(255,255,255,0.75)'; g.font = '700 40px Arial';
    g.fillText('CERTIFICATE OF FIRST BLOCK', 540, 500);
    g.fillStyle = '#D9A441'; g.font = '800 110px Arial';
    g.fillText(REWARD_LABEL, 540, 620);
    g.fillStyle = '#FFFFFF'; g.font = '400 38px Arial';
    g.fillText('Block #' + p.firstHeight.toLocaleString('en-US') + '  ·  ' +
      new Date(p.firstDate).toUTCString().slice(5, 16), 540, 690);
    g.fillStyle = 'rgba(255,255,255,0.65)'; g.font = '400 30px Arial';
    g.fillText(shortAddr, 540, 740);
    g.fillStyle = '#B8863B'; g.font = '700 34px Arial';
    g.fillText(freshBadges.map(function (b) { return b.icon + ' ' + b.name; }).join('   '), 540, 820);
    g.fillStyle = 'rgba(255,255,255,0.8)'; g.font = 'italic 32px Arial';
    g.fillText('Proof-of-work, not proof-of-purchase.', 540, 890);
    g.fillStyle = 'rgba(255,255,255,0.5)'; g.font = '400 28px Arial';
    g.fillText('moonbite.org/mine', 540, 960);
    g.fillStyle = 'rgba(255,255,255,0.35)'; g.font = '400 20px Arial';
    g.fillText('MBITE has no market value and is not an investment. Verified on-chain.', 540, 1005);
    var a = document.createElement('a');
    a.download = 'moonbite-first-block.png';
    a.href = cv.toDataURL('image/png');
    a.click();
  }

  window.MoonBiteBadges = { recordBlocks: recordBlocks, renderShelf: renderShelf };
})();
