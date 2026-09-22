/* Minimal, correct QR Code generator (byte mode, ECC level M).
 * Compact ES-module port of the public-domain qrcode-generator algorithm
 * (Kazuhiko Arase). Produces a real, scannable matrix — no decorative fakes.
 * Exports qrMatrix(text) -> boolean[][] (true = dark module). */

const EXP = new Array(256), LOG = new Array(256);
for (let i = 0; i < 8; i++) EXP[i] = 1 << i;
for (let i = 8; i < 256; i++) EXP[i] = EXP[i-4] ^ EXP[i-5] ^ EXP[i-6] ^ EXP[i-8];
for (let i = 0; i < 255; i++) LOG[EXP[i]] = i;
const gexp = n => { while (n < 0) n += 255; while (n >= 255) n -= 255; return EXP[n]; };
const glog = n => LOG[n];

function polyMul(a, b){
  const r = new Array(a.length + b.length - 1).fill(0);
  for (let i = 0; i < a.length; i++)
    for (let j = 0; j < b.length; j++)
      r[i+j] ^= gexp(glog(a[i]) + glog(b[j]));
  return r;
}
function rsGenerator(n){
  let g = [1];
  for (let i = 0; i < n; i++) g = polyMul(g, [1, gexp(i)]);
  return g;
}
function rsEncode(data, ecCount){
  const gen = rsGenerator(ecCount);
  const res = data.concat(new Array(ecCount).fill(0));
  for (let i = 0; i < data.length; i++){
    const coef = res[i];
    if (coef !== 0)
      for (let j = 0; j < gen.length; j++)
        res[i+j] ^= gexp(glog(gen[j]) + glog(coef));
  }
  return res.slice(data.length);
}

/* Per-version capacity + RS block layout for ECC level M (versions 1..10). */
const M = {
  //      totalDataCodewords, ecPerBlock, [ [numBlocks, dataPerBlock], ... ]
  1:  [16, 10, [[1,16]]],
  2:  [28, 16, [[1,28]]],
  3:  [44, 26, [[1,44]]],
  4:  [64, 18, [[2,32]]],
  5:  [86, 24, [[2,43]]],
  6:  [108, 16, [[4,27]]],
  7:  [124, 18, [[4,31]]],
  8:  [154, 22, [[2,38],[2,39]]],
  9:  [182, 22, [[3,36],[2,37]]],
  10: [216, 26, [[4,43],[1,44]]],
};
const ALIGN = {1:[],2:[6,18],3:[6,22],4:[6,26],5:[6,30],6:[6,34],
  7:[6,22,38],8:[6,24,42],9:[6,26,46],10:[6,28,50]};

function pickVersion(len){
  for (let v = 1; v <= 10; v++){
    const cap = M[v][0] - 2 - ((v >= 10) ? 2 : 1); // minus mode(4b)+count; count is 1 byte for v<10
    if (len <= cap) return v;
  }
  throw new Error('data too long for QR v1..10');
}

function buildData(bytes, version){
  const [totalData] = M[version];
  const bits = [];
  const push = (val, n) => { for (let i = n-1; i >= 0; i--) bits.push((val >> i) & 1); };
  push(0b0100, 4);                       // byte mode
  push(bytes.length, version >= 10 ? 16 : 8);
  for (const b of bytes) push(b, 8);
  push(0, Math.min(4, totalData*8 - bits.length)); // terminator
  while (bits.length % 8) bits.push(0);
  const codewords = [];
  for (let i = 0; i < bits.length; i += 8){
    let c = 0; for (let j = 0; j < 8; j++) c = (c << 1) | bits[i+j];
    codewords.push(c);
  }
  const pads = [0xEC, 0x11];
  let p = 0;
  while (codewords.length < totalData) codewords.push(pads[p++ % 2]);
  return codewords;
}

function interleave(codewords, version){
  const [, ecCount, layout] = M[version];
  const blocks = [];
  let idx = 0;
  for (const [num, dataLen] of layout)
    for (let b = 0; b < num; b++){
      const data = codewords.slice(idx, idx + dataLen); idx += dataLen;
      blocks.push({ data, ec: rsEncode(data, ecCount) });
    }
  const maxData = Math.max(...blocks.map(b => b.data.length));
  const out = [];
  for (let i = 0; i < maxData; i++) for (const b of blocks) if (i < b.data.length) out.push(b.data[i]);
  for (let i = 0; i < ecCount; i++) for (const b of blocks) out.push(b.ec[i]);
  return out;
}

function makeMatrix(version){
  const size = version * 4 + 17;
  const m = Array.from({length:size}, () => new Array(size).fill(null));
  const finder = (r, c) => {
    for (let dr = -1; dr <= 7; dr++) for (let dc = -1; dc <= 7; dc++){
      const rr = r+dr, cc = c+dc; if (rr < 0 || rr >= size || cc < 0 || cc >= size) continue;
      const on = (dr >= 0 && dr <= 6 && (dc === 0 || dc === 6)) ||
                 (dc >= 0 && dc <= 6 && (dr === 0 || dr === 6)) ||
                 (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4);
      m[rr][cc] = on;
    }
  };
  finder(0,0); finder(0,size-7); finder(size-7,0);
  for (let i = 8; i < size-8; i++){ const b = i % 2 === 0; m[6][i] = b; m[i][6] = b; }
  const al = ALIGN[version];
  for (const r of al) for (const c of al){
    if ((r <= 8 && c <= 8) || (r <= 8 && c >= size-9) || (r >= size-9 && c <= 8)) continue;
    for (let dr = -2; dr <= 2; dr++) for (let dc = -2; dc <= 2; dc++)
      m[r+dr][c+dc] = Math.max(Math.abs(dr), Math.abs(dc)) !== 1;
  }
  m[size-8][8] = true; // dark module
  return m;
}

function reserveFormat(m, size){
  const r = [];
  for (let i = 0; i < 9; i++){ if (i !== 6){ r.push([8,i]); r.push([i,8]); } }
  for (let i = size-8; i < size; i++){ r.push([8,i]); r.push([size-1-(i-(size-8)),8]); }
  return r;
}

function placeData(m, data, version){
  const size = m.length;
  const reserved = new Set(reserveFormat(m, size).map(([r,c]) => r+','+c));
  const isFree = (r,c) => m[r][c] === null && !reserved.has(r+','+c);
  let bitIdx = 0; const total = data.length * 8;
  const bitAt = k => (data[k >> 3] >> (7 - (k & 7))) & 1;
  let up = true;
  for (let col = size-1; col > 0; col -= 2){
    if (col === 6) col--;
    for (let i = 0; i < size; i++){
      const row = up ? size-1-i : i;
      for (const c of [col, col-1]){
        if (isFree(row, c)){
          m[row][c] = bitIdx < total ? bitAt(bitIdx) === 1 : false;
          bitIdx++;
        }
      }
    }
    up = !up;
  }
}

function applyMask(m, mask, version){
  const size = m.length;
  const reserved = new Set(reserveFormat(m, size).map(([r,c]) => r+','+c));
  // rebuild a structural map to know which cells are function patterns
  const fn = makeMatrix(version);
  const cond = (r,c) => {
    switch(mask){
      case 0: return (r+c)%2===0; case 1: return r%2===0;
      case 2: return c%3===0; case 3: return (r+c)%3===0;
      case 4: return (Math.floor(r/2)+Math.floor(c/3))%2===0;
      case 5: return (r*c)%2 + (r*c)%3 === 0;
      case 6: return ((r*c)%2 + (r*c)%3)%2===0;
      case 7: return ((r+c)%2 + (r*c)%3)%2===0;
    }
  };
  for (let r = 0; r < size; r++) for (let c = 0; c < size; c++){
    if (fn[r][c] !== null || reserved.has(r+','+c)) continue;
    if (cond(r,c)) m[r][c] = !m[r][c];
  }
}

const FORMAT_BITS = mask => {
  // ECC level M = 0b00, plus 3-bit mask. BCH(15,5) + XOR mask 0x5412.
  const data = (0b00 << 3) | mask;
  let d = data << 10;
  const g = 0b10100110111;
  for (let i = 4; i >= 0; i--) if ((d >> (i+10)) & 1) d ^= g << i;
  return ((data << 10) | d) ^ 0b101010000010010;
};

function placeFormat(m, mask){
  const size = m.length, bits = FORMAT_BITS(mask);
  const get = i => (bits >> i) & 1;
  // around top-left
  for (let i = 0; i <= 5; i++) m[8][i] = get(i) === 1;
  m[8][7] = get(6) === 1; m[8][8] = get(7) === 1; m[7][8] = get(8) === 1;
  for (let i = 9; i <= 14; i++) m[14-i][8] = get(i) === 1;
  // around the other two finders
  for (let i = 0; i <= 7; i++) m[size-1-i][8] = get(i) === 1;
  for (let i = 8; i <= 14; i++) m[8][size-15+i] = get(i) === 1;
}

function penalty(m){
  const size = m.length; let p = 0;
  // simple run-based penalty (rule 1) — enough to pick a decent mask
  for (let r = 0; r < size; r++){
    let run = 1;
    for (let c = 1; c < size; c++){
      if (m[r][c] === m[r][c-1]) { run++; if (run === 5) p += 3; else if (run > 5) p++; }
      else run = 1;
    }
  }
  for (let c = 0; c < size; c++){
    let run = 1;
    for (let r = 1; r < size; r++){
      if (m[r][c] === m[r-1][c]) { run++; if (run === 5) p += 3; else if (run > 5) p++; }
      else run = 1;
    }
  }
  return p;
}

export function qrMatrix(text){
  const bytes = Array.from(new TextEncoder().encode(String(text)));
  const version = pickVersion(bytes.length);
  const codewords = buildData(bytes, version);
  const finalData = interleave(codewords, version);

  let best = null, bestScore = Infinity;
  for (let mask = 0; mask < 8; mask++){
    const m = makeMatrix(version);
    placeData(m, finalData, version);
    applyMask(m, mask, version);
    placeFormat(m, mask);
    // normalize nulls to false
    for (let r = 0; r < m.length; r++) for (let c = 0; c < m.length; c++) if (m[r][c] === null) m[r][c] = false;
    const s = penalty(m);
    if (s < bestScore){ bestScore = s; best = m; }
  }
  return best;
}
