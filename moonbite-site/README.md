# MoonBite ($MBITE) — Landing Site

A one-page, full-viewport, cinematic scroll experience for **MoonBite**. The
signature interaction is a large SVG moon pinned center-stage that loses chunks
("bites") as you scroll — chomp shake, crumb particles, a glowing bite edge —
until only a crescent remains, and that crescent **is** the logo.

Everything is drawn in code (inline SVG + two `<canvas>` layers). No image
assets, no build step, no framework.

---

## Run it

It's a static site — serve the folder with any static server:

```bash
cd moonbite-site
python -m http.server 4173
# open http://localhost:4173
```

(Opening `index.html` directly via `file://` also works, but a server is
recommended so the Google Fonts / CDN requests behave normally.)

---

## Files

| File | Role |
|---|---|
| `index.html` | Semantic markup, inline SVG moon + crescent favicon, all meta/OG tags |
| `styles.css` | Design tokens, layout, the stacking model, responsive + reduced-motion |
| `app.js` | Preloader, custom cursor, starfield/crumb canvas, GSAP/ScrollTrigger scenes, counters |
| `README.md` | This file |

## Stack (CDN-only, pinned)

- **GSAP 3.12.5** + **ScrollTrigger 3.12.5** — scroll-driven timelines & pinning
- **Lenis 1.0.42** — smooth scroll, synced to ScrollTrigger via `gsap.ticker`
- **SplitType 0.3.4** — per-character hero reveal
- **Google Fonts** — Bricolage Grotesque, Instrument Serif, Space Mono
- Vanilla JS otherwise (IIFE, `"use strict"`)

## Design system (strict)

**4 colors only:**

| Token | Hex | Use |
|---|---|---|
| `--void` | `#07070B` | background |
| `--moonmilk` | `#F2EDE4` | moon + primary text |
| `--cheddar` | `#FFC94A` | accent / glow / highlights |
| `--bite` | `#FF3D2E` | the bite / CTA / danger-red |

**3 fonts only:** Bricolage Grotesque (display), Instrument Serif (accent
italic), Space Mono (mono/labels).

## Stacking model

The moon is `position:fixed`. To get the "moon between the two words" look
without one layer trapping the other, the paint order is kept flat against the
root stacking context:

```
stars(1) < hero word-back(2) < moon(3) < hero word-front / content sections(5) < header(40)
```

`main` and `.hero-lockup` intentionally have **no** `z-index` so they don't
create stacking contexts that would trap the hero words above or below the
fixed moon.

## Accessibility & motion

- **Sound is OFF by default.** The WebAudio "chomp" only plays after the user
  toggles it on (`#soundToggle`). It is synthesized (no audio file).
- **`prefers-reduced-motion`**: `app.js` skips all scroll animation and calls
  `staticFallback()`, which renders the final state — crescent fully carved,
  tokenomics rows lit, content visible. No canvas loops churn.
- Custom cursor auto-disables on coarse (touch) pointers.
- Canvas layers are `aria-hidden`; sections are labelled regions.

---

## ⚠️ Placeholders — fill before any public launch

Everything below is a literal `[PLACEHOLDER...]` string in the source. Search
the repo for `PLACEHOLDER` to find them all. **The site must not go live with
these visible.**

| Location (`index.html`) | Placeholder | Needs |
|---|---|---|
| Tokenomics — Supply | `[PLACEHOLDER]` | real max supply (or remove if PoW, see below) |
| Tokenomics — Tax (buy/sell) | `[PLACEHOLDER]` | real values (likely N/A for PoW) |
| Tokenomics — Team allocation | `[PLACEHOLDER]` | real % (0% if truly no premine) |
| Roadmap — CHOMP | `[PLACEHOLDER]` | exchange-conversation wording |
| Roadmap — ECLIPSE | `[PLACEHOLDER]` | closing line |
| Buy — CTA link | `[PLACEHOLDER_WALLET_URL]` | real wallet download/get-wallet page |
| Buy — Live Chain bar | `[PLACEHOLDER_EXPLORER_URL]` | real block-explorer URL |
| Footer — X | `[PLACEHOLDER_X_URL]` | real link |
| Footer — Telegram | `[PLACEHOLDER_TELEGRAM_URL]` | real link |
| Footer — Chart | `[PLACEHOLDER_CHART_URL]` | real link |

---

## 🚩 Honesty flags — read before shipping

MoonBite is a **Litecoin/PoW fork with its own Layer-1 chain** — its own miner,
wallet, block explorer, and native bech32 addresses (`moon…`). A sovereign PoW
chain has **no contract address, no DEX pair, no buy/sell tax, and no liquidity
pool** in the ERC-20 sense.

**The Buy section now tells the PoW story** — get the wallet, point a miner at
the chain, earn block rewards or receive to a `moon…` address, verify in the
explorer. The old meme-token language (contract address, DEX swap, Phantom /
MetaMask, buy/sell tax) has been removed.

**Still inconsistent — clean up before launch:**

- **Tokenomics** still uses token idiom: a fixed `1,000,000,000` supply, a
  **Tax (buy/sell)** row, and **Team allocation**. For a mined PoW coin, replace
  these with chain facts (block reward + halving schedule, block time, real max
  supply, "0% premine"). The actual chain params live in the main repo — pull
  the real numbers from there rather than inventing them.
- **Footer** has a **CHART** link (`[PLACEHOLDER_CHART_URL]`) and a legal line
  calling MBITE a "meme coin." Pre-launch there is no price chart; swap CHART
  for **Explorer** or **GitHub**, and reword the disclaimer to describe an
  experimental PoW cryptocurrency.

These are copy/positioning decisions for the owner, not code bugs — flagged so
they aren't shipped by accident.

No prices, market caps, volumes, or fabricated exchange partnerships appear
anywhere on the page, and none should be added pre-launch.

---

## Creative decisions

- **The moon is the chart.** Tokenomics doesn't use bars or pie slices — each
  scroll-carved bite *is* a data point, so the hero interaction and the data
  viz are the same object.
- **Preloader = a moon filling from shadow**, tying the loading metaphor to the
  eating metaphor before the site even reveals.
- **Two canvases, one rAF loop** (`stars` behind, `crumbs` in front) keep the
  particle work cheap; the loop pauses on `visibilitychange`.
- **Chomp fx is throttled** (260 ms) and fires once per bite so rapid scrolling
  can't machine-gun the shake/sound.
- **Crescent payoff**: the final footer carve leaves exactly the crescent used
  as the favicon and brandmark — the destruction resolves into the logo.
