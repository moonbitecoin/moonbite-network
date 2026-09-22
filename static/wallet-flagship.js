/* MoonBite flagship wallet — app logic.
 * External module (CSP: script-src 'self'); no inline handlers. Reuses the
 * audited crypto modules for all key operations. */
import { generatePhrase, validateMnemonic } from './moonbite-phrase.js';
import { deriveFromSeedPhrase, isValidAddress } from './moonbite-address.js';
import { encryptSeed, decryptSeed, isNewFormat } from './moonbite-crypto.js';
import { buildSignedTransaction } from './moonbite-tx.js';
import { qrMatrix } from './vendor/qr.js';

const $ = s => document.querySelector(s);
const LS = 'mbf_seed_enc';
const FEE = 0.001, UNIT = 1e8;

let seedPhrase = null;      // in-memory only, after create/unlock
let wallet = null;          // { address }
let balanceUnits = 0;
let seedSource = 'create';  // 'create' | 'import' (for PIN back button)
let pinBuf = '', pinStage = 'first', firstPin = '';

/* ---------- navigation ---------- */
function go(id){
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const el = $('#'+id); el.classList.add('active');
  el.scrollTop = 0;
}
function toast(msg){
  $('#toastMsg').textContent = msg; const t = $('#toast');
  t.classList.add('show'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('show'), 1800);
}

/* ---------- onboarding ---------- */
async function startCreate(){
  const phrase = await generatePhrase();
  seedPhrase = phrase; seedSource = 'create';
  const words = phrase.split(/\s+/);
  $('#seedGrid').innerHTML = words.map((w,i) => `<div class="word"><i>${i+1}</i><b>${w}</b></div>`).join('');
  go('s-create');
}
async function doImport(){
  const val = $('#importInput').value.trim().replace(/\s+/g,' ');
  const err = $('#importErr'); err.textContent = '';
  if(!(await validateMnemonic(val))){ err.textContent = 'That is not a valid 12-word recovery phrase.'; return; }
  seedPhrase = val; seedSource = 'import'; startPinSet();
}
function pinBack(){ go(seedSource === 'create' ? 's-create' : 's-import'); }

/* ---------- PIN pads ---------- */
function buildPad(el, onKey){
  const keys = ['1','2','3','4','5','6','7','8','9','','0','del'];
  el.innerHTML = keys.map(k => {
    if(k === '') return '<div class="key ghost"></div>';
    if(k === 'del') return '<button class="key" data-k="del"><svg class="icon"><use href="#i-del"/></svg></button>';
    return `<button class="key" data-k="${k}">${k}</button>`;
  }).join('');
  el.querySelectorAll('.key[data-k]').forEach(b => b.addEventListener('click', () => onKey(b.dataset.k)));
}
function dots(el, n){ el.innerHTML = Array.from({length:6}, (_,i) => `<i class="${i<n?'on':''}"></i>`).join(''); }

function startPinSet(){
  pinBuf = ''; firstPin = ''; pinStage = 'first';
  $('#pinSetTitle').textContent = 'Create a 6-digit PIN';
  $('#pinSetHint').textContent = 'It encrypts your phrase on this device.';
  $('#pinErr').textContent = ''; dots($('#setDots'), 0);
  buildPad($('#setPad'), onSetKey);
  go('s-pin-set');
}
function onSetKey(k){
  if(k === 'del'){ pinBuf = pinBuf.slice(0,-1); dots($('#setDots'), pinBuf.length); return; }
  if(pinBuf.length >= 6) return;
  pinBuf += k; dots($('#setDots'), pinBuf.length);
  if(pinBuf.length < 6) return;
  if(pinStage === 'first'){
    firstPin = pinBuf; pinBuf = ''; pinStage = 'confirm';
    setTimeout(() => { $('#pinSetTitle').textContent = 'Confirm your PIN';
      $('#pinSetHint').textContent = 'Enter it once more.'; dots($('#setDots'), 0); }, 160);
  } else {
    if(pinBuf !== firstPin){
      $('#pinErr').textContent = 'PINs didn’t match — try again.';
      pinBuf = ''; firstPin = ''; pinStage = 'first';
      setTimeout(() => { $('#pinSetTitle').textContent = 'Create a 6-digit PIN';
        $('#pinSetHint').textContent = 'It encrypts your phrase on this device.'; dots($('#setDots'), 0); }, 160);
      return;
    }
    finishSetup(firstPin);
  }
}
async function finishSetup(pin){
  const env = await encryptSeed(seedPhrase, pin);
  localStorage.setItem(LS, env);
  await deriveWallet(); enterHome();
}

/* ---------- unlock ---------- */
function startUnlock(){
  pinBuf = ''; $('#unlockErr').textContent = ''; dots($('#unlockDots'), 0);
  buildPad($('#unlockPad'), onUnlockKey); go('s-unlock');
}
async function onUnlockKey(k){
  if(k === 'del'){ pinBuf = pinBuf.slice(0,-1); dots($('#unlockDots'), pinBuf.length); return; }
  if(pinBuf.length >= 6) return;
  pinBuf += k; dots($('#unlockDots'), pinBuf.length);
  if(pinBuf.length < 6) return;
  const seed = await decryptSeed(localStorage.getItem(LS), pinBuf);
  if(!seed){ $('#unlockErr').textContent = 'Wrong PIN'; pinBuf = '';
    setTimeout(() => dots($('#unlockDots'), 0), 300); return; }
  seedPhrase = seed; await deriveWallet(); enterHome();
}

/* ---------- wallet ---------- */
async function deriveWallet(){ const d = await deriveFromSeedPhrase(seedPhrase); wallet = { address: d.address }; }
function realAddress(){ return (wallet && wallet.address && isValidAddress(wallet.address)) ? wallet.address : null; }
function enterHome(){ go('s-home'); renderHome(); refreshBalance(); }

function fmt(units){ return (units/UNIT).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:8}); }
function renderHome(){
  $('#balNum').textContent = fmt(balanceUnits);
  $('#balSpend').textContent = fmt(balanceUnits);
  $('#sendAvail').textContent = fmt(balanceUnits);
}
async function refreshBalance(){
  const a = realAddress(); if(!a) return;
  try{
    const r = await fetch('/api/chain/address/' + encodeURIComponent(a));
    const j = await r.json();
    balanceUnits = (j.total_units ?? j.confirmed_units ?? j.balance_units ?? 0) || 0;
  }catch(e){ /* offline: keep last known */ }
  renderHome();
}

/* ---------- receive ---------- */
function openReceive(){
  const a = realAddress(); if(!a){ toast('Unlock your wallet first'); return; }
  $('#recvAddr').innerHTML = a.replace(/^(moon1)(.*)(.{6})$/, '<span class="hl">$1</span>$2<span class="hl">$3</span>');
  renderQR(a, $('#qrFrame'));
  go('s-receive');
}
async function copyAddr(){
  const a = realAddress(); if(!a) return;
  try{ await navigator.clipboard.writeText(a); toast('Address copied'); }
  catch(e){ toast('Copy failed'); }
}
function renderQR(text, frame){
  try{
    const m = qrMatrix(text), n = m.length, S = 190, cell = S/n, NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', `0 0 ${S} ${S}`);
    const bg = document.createElementNS(NS, 'rect'); bg.setAttribute('width', S); bg.setAttribute('height', S); bg.setAttribute('fill', '#F5F2EA'); svg.appendChild(bg);
    let d = '';
    for(let y=0;y<n;y++) for(let x=0;x<n;x++) if(m[y][x]) d += `M${(x*cell).toFixed(2)} ${(y*cell).toFixed(2)}h${cell.toFixed(2)}v${cell.toFixed(2)}h${(-cell).toFixed(2)}z`;
    const p = document.createElementNS(NS, 'path'); p.setAttribute('d', d); p.setAttribute('fill', '#0A0C11'); svg.appendChild(p);
    frame.innerHTML = ''; frame.appendChild(svg);
  }catch(e){
    frame.innerHTML = '<div style="color:#20170A;font-size:12px;padding:14px;text-align:center;line-height:1.5">Copy the address below</div>';
  }
}

/* ---------- send ---------- */
function onSendInput(){
  const amt = parseFloat($('#sendAmt').value) || 0;
  const to = $('#sendTo').value.trim();
  $('#sendReview').style.display = amt > 0 ? 'block' : 'none';
  $('#rvAmt').textContent = amt.toLocaleString('en-US', {maximumFractionDigits:8});
  $('#rvTot').textContent = (amt + FEE).toLocaleString('en-US', {maximumFractionDigits:8});
  $('#sendBtn').disabled = !(amt > 0 && to.length > 6);
  $('#sendErr').textContent = '';
}
function sendMax(){ const max = Math.max(0, balanceUnits/UNIT - FEE); $('#sendAmt').value = max > 0 ? +max.toFixed(8) : '0'; onSendInput(); }
async function doSend(){
  const amt = parseFloat($('#sendAmt').value) || 0, to = $('#sendTo').value.trim(), err = $('#sendErr');
  err.textContent = '';
  if(!isValidAddress(to)){ err.textContent = 'That doesn’t look like a valid MoonBite address.'; return; }
  const amountUnits = Math.round(amt * UNIT), feeUnits = Math.round(FEE * UNIT);
  if(amountUnits <= 0){ err.textContent = 'Enter an amount to send.'; return; }
  if(amountUnits + feeUnits > balanceUnits){ err.textContent = 'Not enough MBITE for that amount plus the fee.'; return; }
  const a = realAddress();
  if(!a || !seedPhrase){ err.textContent = 'Unlock your wallet first.'; return; }

  const btn = $('#sendBtn'), label = btn.textContent;
  btn.disabled = true; btn.textContent = 'Sending…';
  try{
    // Real spend: fetch this wallet's UTXOs, sign ON DEVICE with the audited
    // builder, and broadcast the finished hex. The seed never leaves the page.
    const r = await fetch('/api/chain/address/' + encodeURIComponent(a));
    const j = await r.json();
    const utxos = j.utxos || [];
    const built = await buildSignedTransaction({ seedPhrase, toAddress: to, amountUnits, feeUnits, utxos });
    const br = await fetch('/api/chain/broadcast', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rawtx: built.rawHex }),
    });
    const bj = await br.json();
    if(!br.ok || bj.status !== 'success') throw new Error(bj.message || 'The network rejected this transaction.');
    $('#sendAmt').value = ''; $('#sendTo').value = ''; onSendInput();
    toast('Sent'); go('s-home'); setTimeout(refreshBalance, 1500);
  }catch(e){
    err.textContent = (e && e.message) ? e.message : 'Send failed. Please try again.';
  }finally{
    btn.disabled = false; btn.textContent = label;
  }
}

/* ---------- event delegation (CSP-safe: no inline handlers) ---------- */
const ACTIONS = { go: (a) => go(a), startCreate, doImport, toPin: startPinSet, pinBack,
  openReceive, copyAddr, refreshBalance, sendMax, doSend };
document.addEventListener('click', e => {
  const el = e.target.closest('[data-act]'); if(!el) return;
  const fn = ACTIONS[el.dataset.act]; if(fn) fn(el.dataset.arg);
});
$('#sendAmt').addEventListener('input', onSendInput);
$('#sendTo').addEventListener('input', onSendInput);

/* ---------- boot ---------- */
(function boot(){
  const env = localStorage.getItem(LS);
  if(env && isNewFormat(env)) startUnlock(); else go('s-welcome');
})();
