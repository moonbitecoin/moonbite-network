/* ============================================================
   MoonBite ($MBITE) — app.js
   GSAP + ScrollTrigger + Lenis + SplitType. Vanilla otherwise.
   ============================================================ */
(() => {
  "use strict";

  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TOUCH = window.matchMedia("(pointer: coarse)").matches;
  const MOBILE = window.matchMedia("(max-width: 760px)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  document.getElementById("year").textContent = new Date().getFullYear();

  /* ---------------------------------------------------------
     WEBAUDIO CHOMP  (off by default)
  --------------------------------------------------------- */
  let audioCtx = null, soundOn = false;
  const soundBtn = $("#soundToggle");
  function ensureCtx(){ if(!audioCtx){ try{ audioCtx = new (window.AudioContext||window.webkitAudioContext)(); }catch(e){} } }
  function chompSound(){
    if(!soundOn || !audioCtx) return;
    const t = audioCtx.currentTime;
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sawtooth";
    o.frequency.setValueAtTime(180, t);
    o.frequency.exponentialRampToValueAtTime(48, t + 0.12);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.22, t + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    o.connect(g); g.connect(audioCtx.destination);
    o.start(t); o.stop(t + 0.18);
  }
  if(soundBtn){
    soundBtn.addEventListener("click", () => {
      soundOn = !soundOn; ensureCtx();
      if(audioCtx && audioCtx.state === "suspended") audioCtx.resume();
      soundBtn.textContent = "SOUND: " + (soundOn ? "ON" : "OFF");
      soundBtn.setAttribute("aria-pressed", String(soundOn));
      if(soundOn) chompSound();
    });
  }

  /* ---------------------------------------------------------
     CUSTOM CURSOR (teeth)
  --------------------------------------------------------- */
  const cursor = $("#cursor");
  if(cursor && !TOUCH){
    let cx = innerWidth/2, cy = innerHeight/2, tx = cx, ty = cy;
    addEventListener("mousemove", e => { tx = e.clientX; ty = e.clientY; }, {passive:true});
    (function loop(){
      cx += (tx-cx)*0.28; cy += (ty-cy)*0.28;
      cursor.style.transform = `translate(${cx}px,${cy}px) translate(-50%,-50%)`;
      requestAnimationFrame(loop);
    })();
    const hot = "a,button,.cta,.mega-links a,.crescent-logo,#copyBtn,.sound-toggle,[data-hot]";
    document.addEventListener("mouseover", e => { if(e.target.closest(hot)) cursor.classList.add("hot"); });
    document.addEventListener("mouseout", e => { if(e.target.closest(hot)) cursor.classList.remove("hot"); });
    document.addEventListener("mousedown", () => cursor.classList.add("bite"));
    document.addEventListener("mouseup", () => cursor.classList.remove("bite"));
  }

  /* ---------------------------------------------------------
     STARFIELD (3-depth parallax) + CRUMBS — one rAF loop
  --------------------------------------------------------- */
  const starCv = $("#stars"), sctx = starCv.getContext("2d");
  const crumbCv = $("#crumbs"), cctx = crumbCv.getContext("2d");
  let stars = [], crumbs = [], W=0, H=0, dpr=Math.min(devicePixelRatio||1,2);
  let pmx=0, pmy=0; // parallax mouse
  function resize(){
    W = innerWidth; H = innerHeight;
    [starCv, crumbCv].forEach(c => { c.width = W*dpr; c.height = H*dpr; c.style.width=W+"px"; c.style.height=H+"px"; });
    sctx.setTransform(dpr,0,0,dpr,0,0); cctx.setTransform(dpr,0,0,dpr,0,0);
    const count = MOBILE ? 70 : 190;
    stars = Array.from({length:count}, () => {
      const depth = Math.random(); // 0..1
      return { x:Math.random()*W, y:Math.random()*H, z:0.4+depth*2.2, r:0.3+depth*1.6, tw:Math.random()*Math.PI*2 };
    });
  }
  resize(); addEventListener("resize", resize);
  if(!TOUCH){ addEventListener("mousemove", e => { pmx=(e.clientX/W-0.5); pmy=(e.clientY/H-0.5); }, {passive:true}); }

  function spawnCrumbs(sx, sy, n){
    if(REDUCED) return;
    const N = MOBILE ? Math.round(n*0.5) : n;
    for(let i=0;i<N;i++){
      crumbs.push({
        x:sx, y:sy,
        vx:(Math.random()-0.5)*3.2,
        vy:-1.4 - Math.random()*2.6,
        r:0.8+Math.random()*2.4,
        life:1, decay:0.004+Math.random()*0.006,
        c: Math.random()<0.22 ? "#FFC94A" : "#E7DCC4"
      });
    }
  }

  let starPaused = false;
  document.addEventListener("visibilitychange", () => { starPaused = document.hidden; });
  function frame(){
    if(!starPaused){
      sctx.clearRect(0,0,W,H);
      for(const s of stars){
        s.tw += 0.02;
        const px = s.x + (REDUCED?0:pmx*30*s.z);
        const py = s.y + (REDUCED?0:pmy*30*s.z);
        const a = 0.35 + Math.sin(s.tw)*0.3;
        sctx.globalAlpha = Math.max(0.05,a);
        sctx.fillStyle = s.z>1.8 ? "#FFC94A" : "#F2EDE4";
        sctx.beginPath(); sctx.arc(px,py,s.r,0,6.283); sctx.fill();
      }
      sctx.globalAlpha = 1;

      // crumbs
      cctx.clearRect(0,0,W,H);
      for(let i=crumbs.length-1;i>=0;i--){
        const p = crumbs[i];
        p.x+=p.vx; p.y+=p.vy; p.vy+=0.012; p.vx*=0.99; p.life-=p.decay;
        if(p.life<=0){ crumbs.splice(i,1); continue; }
        cctx.globalAlpha = Math.max(0,p.life);
        cctx.fillStyle = p.c;
        cctx.beginPath(); cctx.arc(p.x,p.y,p.r,0,6.283); cctx.fill();
      }
      cctx.globalAlpha = 1;
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  /* ---------------------------------------------------------
     CHOMP: screen shake + edge glow + crumbs + sound (throttled)
  --------------------------------------------------------- */
  const shaker = $("#moonShaker");
  const biteEdge = $("#biteEdge");
  const moonSvg = $("#moonSvg");
  let lastChomp = 0;
  function chomp(biteCircle){
    const now = performance.now();
    if(now - lastChomp < 260) return; // throttle
    lastChomp = now;

    chompSound();

    if(!REDUCED && shaker){
      const seq = [[4,-3],[-5,3],[3,4],[-3,-2],[0,0]];
      let i=0;
      (function step(){
        if(i>=seq.length){ shaker.style.transform="translate(0,0)"; return; }
        shaker.style.transform = `translate(${seq[i][0]}px,${seq[i][1]}px)`;
        i++; setTimeout(step, 16);
      })();
    }

    // edge glow + crumbs from the bite's screen position
    if(biteCircle){
      const cxAttr = +biteCircle.getAttribute("cx");
      const cyAttr = +biteCircle.getAttribute("cy");
      const rAttr  = Math.max(40, +biteCircle.getAttribute("r"));
      if(biteEdge && !REDUCED){
        biteEdge.setAttribute("cx", cxAttr);
        biteEdge.setAttribute("cy", cyAttr);
        biteEdge.setAttribute("r", rAttr);
        biteEdge.style.opacity = "1";
        gsapFade(biteEdge);
      }
      // convert SVG coords -> screen for crumbs
      if(moonSvg){
        const rect = moonSvg.getBoundingClientRect();
        const sx = rect.left + (cxAttr/600)*rect.width;
        const sy = rect.top + (cyAttr/600)*rect.height;
        spawnCrumbs(sx, sy, 26);
      }
    }
  }
  function gsapFade(el){
    if(window.gsap){ gsap.to(el, {opacity:0, duration:0.5, ease:"power2.out"}); }
    else { setTimeout(()=>{el.style.opacity="0";}, 300); }
  }

  /* ---------------------------------------------------------
     PRELOADER
  --------------------------------------------------------- */
  const preShadow = $("#preShadow");
  const preNum = $("#preNum");
  const moonStage = $("#moonStage");
  const body = document.body;

  function revealSite(){
    body.classList.add("loaded");
    if(moonStage){ moonStage.style.transition="opacity .8s ease"; moonStage.style.opacity="1"; }
    initScroll();
    heroIntro();
  }

  function runPreloader(){
    if(REDUCED){ revealSite(); return; }
    let p = 0;
    const dur = 1700, t0 = performance.now();
    function tick(now){
      p = Math.min(1, (now - t0)/dur);
      const eased = 1-Math.pow(1-p,3);
      preNum.textContent = Math.round(eased*100);
      // shadow width 144 -> 0 as it "fills"
      if(preShadow) preShadow.setAttribute("width", String(144*(1-eased)));
      if(p<1){ requestAnimationFrame(tick); }
      else firstBite();
    }
    requestAnimationFrame(tick);
  }

  function firstBite(){
    // first bite on the preloader moon: quick crumb burst + shake, then curtains
    const preMoon = $(".pre-moon");
    ensureCtx(); chompSound();
    if(preMoon){
      const r = preMoon.getBoundingClientRect();
      spawnCrumbs(r.left+r.width*0.72, r.top+r.height*0.32, 30);
      preMoon.animate(
        [{transform:"translate(0,0)"},{transform:"translate(5px,-3px)"},{transform:"translate(-4px,3px)"},{transform:"translate(0,0)"}],
        {duration:120, easing:"ease-out"}
      );
    }
    const cL = $(".pre-curtain-l"), cR = $(".pre-curtain-r");
    setTimeout(()=>{
      if(window.gsap){
        gsap.to(cL,{xPercent:-100,duration:0.9,ease:"power4.inOut"});
        gsap.to(cR,{xPercent:100,duration:0.9,ease:"power4.inOut"});
        gsap.to(".pre-core",{scale:0.4,opacity:0,duration:0.7,ease:"power3.in"});
        gsap.delayedCall(0.55, revealSite);
      } else {
        cL.style.transform="translateX(-100%)"; cR.style.transform="translateX(100%)";
        setTimeout(revealSite,600);
      }
    }, 140);
  }

  /* ---------------------------------------------------------
     HERO INTRO — SplitType stagger
  --------------------------------------------------------- */
  function heroIntro(){
    if(REDUCED || !window.SplitType || !window.gsap) return;
    $$(".wordmark .word").forEach((w, wi) => {
      const split = new SplitType(w, {types:"chars"});
      gsap.from(split.chars, {
        yPercent:120, rotate:8, opacity:0, duration:1.1, ease:"expo.out",
        stagger:0.045, delay:0.1 + wi*0.12
      });
    });
    gsap.from(".hero-sub", {opacity:0, y:20, duration:1, ease:"expo.out", delay:0.6});
    gsap.from(".scrollcue", {opacity:0, duration:1, delay:1});
  }

  /* ---------------------------------------------------------
     MARQUEE — seamless, slows on hover (not stop)
  --------------------------------------------------------- */
  const marqueeTrack = $("#marqueeTrack");
  if(marqueeTrack && !REDUCED){
    let mx = 0, speed = 0.6, target = 0.6, half = 0;
    const measure = () => { half = marqueeTrack.scrollWidth/2; };
    measure(); addEventListener("resize", measure);
    const wrap = $(".marquee");
    wrap.addEventListener("mouseenter", ()=> target = 0.15);
    wrap.addEventListener("mouseleave", ()=> target = 0.6);
    (function m(){
      speed += (target-speed)*0.05;
      mx -= speed;
      if(half && -mx >= half) mx += half;
      marqueeTrack.style.transform = `translateX(${mx}px)`;
      requestAnimationFrame(m);
    })();
  }

  /* ---------------------------------------------------------
     SCROLL — Lenis + ScrollTrigger + bite choreography
  --------------------------------------------------------- */
  const bites = $$(".bite");            // 5 edge nibbles
  const crescentCarve = $("#crescentCarve");
  const miniCarve = $("#miniCarve");
  const firedBite = new Set();

  // target radii for each edge bite when "fully taken"
  const BITE_R = [78, 70, 74, 66, 60];

  function initScroll(){
    if(REDUCED || !window.gsap || !window.ScrollTrigger){ staticFallback(); return; }
    gsap.registerPlugin(ScrollTrigger);

    // Lenis smooth scroll
    let lenis = null;
    if(window.Lenis){
      lenis = new Lenis({ lerp: 0.08, smoothWheel:true });
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add((t)=> lenis.raf(t*1000));
      gsap.ticker.lagSmoothing(0);
    }

    /* ---- MOON stage subtle scale/drift through the page ---- */
    gsap.to(".moon-svg", {
      scrollTrigger:{ trigger:"main", start:"top top", end:"bottom bottom", scrub:1 },
      scale:0.62, ease:"none"
    });

    /* ---- STORY: reveal beat lines + take bites 1 & 2 ---- */
    $$(".beat").forEach(beat => {
      const lines = $$(".beat-line", beat);
      lines.forEach(l=>{ const s=new SplitType(l,{types:"lines"}); s.lines.forEach(ln=>ln.classList.add("ln")); });
      gsap.from($$(".ln > *", beat).length ? $$(".ln", beat) : lines, {
        scrollTrigger:{ trigger:beat, start:"top 78%", end:"top 40%", scrub:false, toggleActions:"play none none reverse" },
        yPercent:110, opacity:0, duration:1, ease:"expo.out", stagger:0.12
      });
    });

    // bite 1 grows across story beat 2, bite 2 across beat 3
    biteScrub(bites[0], "[data-beat='2']", "top 80%", "center 55%", 0);
    biteScrub(bites[1], "[data-beat='3']", "top 80%", "center 55%", 1);

    /* ---- TOKENOMICS: light rows + carve bites 3,4,5 ---- */
    const rows = $$(".tk-row");
    rows.forEach((row, i) => {
      ScrollTrigger.create({
        trigger: row, start:"top 82%",
        onEnter:()=>{ row.classList.add("lit"); countUp(row); if(i>=1 && bites[i+1]) growBite(i+1); },
        onLeaveBack:()=> row.classList.remove("lit")
      });
    });
    /* bites 3,4,5 are carved by growBite() as each row lights up (above) —
       no scrub here, that double-drove the same mask circles and caused jank */

    /* ---- ROADMAP: horizontal pan + mini-moon eaten ---- */
    const rmTrack = $("#rmTrack");
    if(rmTrack){
      const panDist = () => rmTrack.scrollWidth - innerWidth + (MOBILE?40:0);
      const pan = gsap.to(rmTrack, {
        x: () => -panDist(),
        ease:"none",
        scrollTrigger:{
          trigger:"#roadmap", start:"top top", end:()=> "+="+panDist(),
          scrub:1, pin:".rm-pin", anticipatePin:1, invalidateOnRefresh:true,
          onUpdate:(self)=>{ if(miniCarve) miniCarve.setAttribute("r", String(self.progress*16)); }
        }
      });
    }

    /* ---- BUY: steps clip-wipe in ---- */
    $$(".step").forEach((st,i)=>{
      ScrollTrigger.create({ trigger:st, start:"top 85%",
        onEnter:()=> gsap.to(st,{clipPath:"inset(0 0% 0 0)", duration:0.7, ease:"power4.inOut", delay:i*0.04, onStart:()=>st.classList.add("in")}) });
    });

    // magnetic CTA
    magnetic($("#cta"));

    /* ---- FOOTER: final crescent carve ---- */
    biteScrub(crescentCarve, "#footer", "top 85%", "top 30%", -1, 150);

    ScrollTrigger.refresh();
  }

  // scrub a single bite circle's radius from 0 -> target as trigger scrolls
  function biteScrub(circle, trigger, start, end, biteIdx, maxR){
    if(!circle) return;
    const targetR = maxR != null ? maxR : (biteIdx>=0 ? BITE_R[biteIdx] : 150);
    ScrollTrigger.create({
      trigger, start, end, scrub:true,
      onUpdate:(self)=>{
        const r = self.progress*targetR;
        circle.setAttribute("r", String(r));
        if(biteIdx>=0){
          if(!firedBite.has(biteIdx) && self.progress>0.35){ firedBite.add(biteIdx); chomp(circle); }
        }
      }
    });
  }
  function growBite(idx){
    const c = bites[idx]; if(!c) return;
    if(window.gsap){
      gsap.to(c, {attr:{r:BITE_R[idx]}, duration:0.7, ease:"power3.out"});
      if(!firedBite.has(idx)){ firedBite.add(idx); chomp(c); }
    } else { c.setAttribute("r", BITE_R[idx]); }
  }

  /* ---------------------------------------------------------
     COUNTERS (tabular)
  --------------------------------------------------------- */
  const counted = new Set();
  function countUp(scope){
    $$(".count", scope).forEach(el=>{
      if(counted.has(el)) return; counted.add(el);
      const to = +el.dataset.to || 0;
      if(to===0){ el.textContent = "0"; return; }
      const obj = {v:0};
      if(window.gsap){
        gsap.to(obj,{v:to, duration:1.6, ease:"power2.out",
          onUpdate:()=> el.textContent = Math.round(obj.v).toLocaleString("en-US")});
      } else el.textContent = to.toLocaleString("en-US");
    });
  }

  /* ---------------------------------------------------------
     MAGNETIC BUTTON
  --------------------------------------------------------- */
  function magnetic(el){
    if(!el || TOUCH || REDUCED || !window.gsap) return;
    const strength = 0.4;
    el.addEventListener("mousemove", e=>{
      const r = el.getBoundingClientRect();
      const mx = e.clientX - (r.left+r.width/2);
      const my = e.clientY - (r.top+r.height/2);
      gsap.to(el,{x:mx*strength, y:my*strength, duration:0.4, ease:"power3.out"});
    });
    el.addEventListener("mouseleave", ()=> gsap.to(el,{x:0,y:0,duration:0.5,ease:"elastic.out(1,0.4)"}));
  }

  /* ---------------------------------------------------------
     EXPLORER-LINK COPY — with "bite" on last 4 chars
  --------------------------------------------------------- */
  const copyBtn = $("#copyBtn"), addrEl = $("#contractAddr");
  if(copyBtn && addrEl){
    copyBtn.addEventListener("click", async ()=>{
      const full = addrEl.dataset.full || addrEl.textContent;
      try{ await navigator.clipboard.writeText(full); }catch(e){}
      chomp(null); chompSound();
      const txt = full;
      const head = txt.slice(0, Math.max(0, txt.length-4));
      const tail = txt.slice(-4);
      addrEl.innerHTML = head + '<span class="nibbled">'+tail+'</span>';
      copyBtn.textContent = "COPIED"; copyBtn.classList.add("copied");
      setTimeout(()=>{ addrEl.textContent = txt; copyBtn.textContent="COPY"; copyBtn.classList.remove("copied"); }, 1400);
    });
  }

  /* ---------------------------------------------------------
     EASTER EGG — crescent takes one more crumb-bite
  --------------------------------------------------------- */
  const crescent = $("#crescentLogo");
  if(crescent){
    const jokes = ["we said we'd finish it.","just a nibble. for the road.","the sun looks tasty too.","burp."];
    let ji = 0;
    crescent.addEventListener("click", ()=>{
      const r = crescent.getBoundingClientRect();
      spawnCrumbs(r.left+r.width*0.6, r.top+r.height*0.4, 16);
      chomp(null); chompSound();
      const note = document.createElement("span");
      note.textContent = jokes[ji++ % jokes.length];
      note.setAttribute("aria-live","polite");
      note.style.cssText = "display:block;margin-top:12px;font-family:var(--f-serif);font-style:italic;color:var(--cheddar);font-size:20px;opacity:0;transition:opacity .4s";
      crescent.parentNode.appendChild(note);
      requestAnimationFrame(()=> note.style.opacity="1");
      setTimeout(()=>{ note.style.opacity="0"; setTimeout(()=>note.remove(),400); }, 2200);
    });
  }

  /* ---------------------------------------------------------
     REDUCED-MOTION / no-GSAP FALLBACK
  --------------------------------------------------------- */
  function staticFallback(){
    // show moon as final crescent: grow the big carve statically
    if(crescentCarve) crescentCarve.setAttribute("r","150");
    bites.forEach((b,i)=> b.setAttribute("r", String(BITE_R[i]*0.6)));
    // reveal counters + rows
    $$(".tk-row").forEach(r=>r.classList.add("lit"));
    $$(".count").forEach(el=>{ const to=+el.dataset.to||0; el.textContent = to.toLocaleString("en-US"); });
    $$(".step").forEach(s=>s.classList.add("in"));
  }

  /* ---------------------------------------------------------
     GO
  --------------------------------------------------------- */
  if(document.readyState === "complete") runPreloader();
  else addEventListener("load", runPreloader);
  // safety: never trap the user behind a stuck preloader
  setTimeout(()=>{ if(!body.classList.contains("loaded")) revealSite(); }, 4500);

})();
