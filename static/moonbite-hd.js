/* BIP32 HD key derivation for MoonBite (native-segwit BIP84 path).
 *
 * Turns a BIP39 seed into private keys along m/84'/2'/0'/0/i, and a public key
 * into the P2WPKH pubkey-hash the chain uses (RIPEMD160(SHA256(pubkey))).
 * secp256k1 point math comes from the vendored noble library; SHA-512/HMAC/
 * SHA-256 from WebCrypto; RIPEMD160 is implemented here (WebCrypto lacks it).
 */
import { getPublicKey } from './vendor/noble-secp256k1.js?v=20260904a';

const N = BigInt('0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141');
const enc = new TextEncoder();

function hexToBytes(h){const a=new Uint8Array(h.length/2);for(let i=0;i<a.length;i++)a[i]=parseInt(h.substr(i*2,2),16);return a;}
function bytesToHex(b){let s='';for(const x of b)s+=x.toString(16).padStart(2,'0');return s;}
function concat(...a){let n=0;for(const x of a)n+=x.length;const o=new Uint8Array(n);let i=0;for(const x of a){o.set(x,i);i+=x.length;}return o;}

async function sha256(b){return new Uint8Array(await crypto.subtle.digest('SHA-256',b));}
async function hmac512(key,data){
    const k=await crypto.subtle.importKey('raw',key,{name:'HMAC',hash:'SHA-512'},false,['sign']);
    return new Uint8Array(await crypto.subtle.sign('HMAC',k,data));
}

/* --- RIPEMD160 (compact, public-domain style implementation) --- */
function rmd160(msg){
  const rol=(x,n)=>((x<<n)|(x>>>(32-n)))>>>0;
  const f=(j,x,y,z)=> j<16?(x^y^z):j<32?((x&y)|(~x&z)):j<48?((x|~y)^z):j<64?((x&z)|(y&~z)):(x^(y|~z));
  const K=[0,0x5a827999,0x6ed9eba1,0x8f1bbcdc,0xa953fd4e];
  const KK=[0x50a28be6,0x5c4dd124,0x6d703ef3,0x7a6d76e9,0];
  const r=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13];
  const rr=[5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11];
  const s=[11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6];
  const ss=[8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11];
  const len=msg.length;const nblk=((len+8)>>6)+1;const X=new Int32Array(nblk*16);
  for(let i=0;i<len;i++)X[i>>2]|=msg[i]<<(8*(i%4));
  X[len>>2]|=0x80<<(8*(len%4));X[nblk*16-2]=len<<3;
  let h0=0x67452301,h1=0xefcdab89,h2=0x98badcfe,h3=0x10325476,h4=0xc3d2e1f0;
  for(let i=0;i<nblk;i++){
    let a1=h0,b1=h1,c1=h2,d1=h3,e1=h4,a2=h0,b2=h1,c2=h2,d2=h3,e2=h4;
    for(let j=0;j<80;j++){
      let t=(a1+f(j,b1,c1,d1)+X[i*16+r[j]]+K[(j/16)|0])>>>0;t=(rol(t,s[j])+e1)>>>0;
      a1=e1;e1=d1;d1=rol(c1,10);c1=b1;b1=t;
      t=(a2+f(79-j,b2,c2,d2)+X[i*16+rr[j]]+KK[(j/16)|0])>>>0;t=(rol(t,ss[j])+e2)>>>0;
      a2=e2;e2=d2;d2=rol(c2,10);c2=b2;b2=t;
    }
    const t=(h1+c1+d2)>>>0;h1=(h2+d1+e2)>>>0;h2=(h3+e1+a2)>>>0;h3=(h4+a1+b2)>>>0;h4=(h0+b1+c2)>>>0;h0=t;
  }
  const out=new Uint8Array(20);const hs=[h0,h1,h2,h3,h4];
  for(let i=0;i<5;i++){out[i*4]=hs[i]&255;out[i*4+1]=(hs[i]>>>8)&255;out[i*4+2]=(hs[i]>>>16)&255;out[i*4+3]=(hs[i]>>>24)&255;}
  return out;
}

export async function hash160(bytes){ return rmd160(await sha256(bytes)); }

function ser32(i){return new Uint8Array([(i>>>24)&255,(i>>>16)&255,(i>>>8)&255,i&255]);}
function ser256(n){return hexToBytes(n.toString(16).padStart(64,'0'));}
function be(bytes){return BigInt('0x'+bytesToHex(bytes));}

async function master(seed){
    const I=await hmac512(enc.encode('Bitcoin seed'),seed);
    return {k:I.slice(0,32),c:I.slice(32)};
}
async function ckd(node,i){
    let data;
    if(i>=0x80000000){ data=concat(new Uint8Array([0]),node.k,ser32(i)); }
    else { data=concat(getPublicKey(node.k,true),ser32(i)); }
    const I=await hmac512(node.c,data);
    const ki=(be(I.slice(0,32))+be(node.k))%N;
    if(ki===0n) throw new Error('invalid derived key');
    return {k:ser256(ki),c:I.slice(32)};
}

/* Derive a key node at a BIP32 path like "m/84'/2'/0'/0/0". */
export async function derivePath(seed,path){
    let node=await master(seed);
    for(const seg of path.split('/').slice(1)){
        const hard=seg.endsWith("'")||seg.endsWith('h');
        const idx=parseInt(hard?seg.slice(0,-1):seg,10)+(hard?0x80000000:0);
        node=await ckd(node,idx);
    }
    return node;
}

/* Full account key for MoonBite native segwit, index i on the external chain. */
export async function deriveKey(seed,i=0){
    const node=await derivePath(seed,"m/84'/2'/0'/0/"+i);
    const priv=bytesToHex(node.k);
    const pub=bytesToHex(getPublicKey(node.k,true));
    return { privkey:priv, pubkey:pub };
}

export { bytesToHex, hexToBytes };
