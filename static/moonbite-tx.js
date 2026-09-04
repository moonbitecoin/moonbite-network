/* MoonBite transaction building and signing — real Bitcoin-family segwit.
 *
 * Builds a standard P2WPKH (native segwit) transaction and signs each input
 * with BIP143, exactly as MoonBite Core validates. The private key never
 * leaves the browser; only the finished raw transaction is broadcast.
 *
 * Single-key wallet: every UTXO is on the wallet's own key (m/84'/2'/0'/0/0),
 * so one key signs all inputs.
 */
import { getPublicKey, signAsync } from './vendor/noble-secp256k1.js?v=20260904a';
import { hash160, bytesToHex, hexToBytes } from './moonbite-hd.js?v=20260904a';
import { pubkeyHashFromAddress, privkeyFromSeedPhrase } from './moonbite-address.js?v=20260904a';

const enc = new TextEncoder();
function concat(...a){let n=0;for(const x of a)n+=x.length;const o=new Uint8Array(n);let i=0;for(const x of a){o.set(x,i);i+=x.length;}return o;}
function u32le(n){return new Uint8Array([n&255,(n>>>8)&255,(n>>>16)&255,(n>>>24)&255]);}
function u64le(v){const o=new Uint8Array(8);let n=BigInt(v);for(let i=0;i<8;i++){o[i]=Number(n&255n);n>>=8n;}return o;}
function varint(n){if(n<0xfd)return new Uint8Array([n]);if(n<=0xffff)return concat(new Uint8Array([0xfd]),new Uint8Array([n&255,(n>>8)&255]));return concat(new Uint8Array([0xfe]),u32le(n));}
function revHex(h){return hexToBytes(h).reverse();}
async function sha256(b){return new Uint8Array(await crypto.subtle.digest('SHA-256',b));}
async function dsha256(b){return sha256(await sha256(b));}

/* scriptPubKey for a P2WPKH address (moon1…): OP_0 <20-byte hash>. */
function spkFromPubkeyHash(pkhHex){return concat(new Uint8Array([0x00,0x14]),hexToBytes(pkhHex));}
/* scriptCode for signing a P2WPKH input: the classic P2PKH script. */
function scriptCode(pkhHex){return concat(new Uint8Array([0x19,0x76,0xa9,0x14]),hexToBytes(pkhHex),new Uint8Array([0x88,0xac]));}

function bigToMinimal(x){
    let h=x.toString(16); if(h.length%2)h='0'+h;
    let b=hexToBytes(h);
    if(b.length && (b[0]&0x80)) b=concat(new Uint8Array([0]),b);
    return b;
}
function derSig(r,s){
    const R=bigToMinimal(r), S=bigToMinimal(s);
    const body=concat(new Uint8Array([0x02,R.length]),R,new Uint8Array([0x02,S.length]),S);
    return concat(new Uint8Array([0x30,body.length]),body);
}

export function selectUTXOs(utxos,target){
    const sorted=[...utxos].sort((a,b)=>b.value-a.value);
    const chosen=[]; let total=0;
    for(const u of sorted){chosen.push(u);total+=u.value;if(total>=target)break;}
    return {chosen,total};
}

/* Build + sign. Returns { rawHex, txid, fee, change }. Amounts in base units. */
export async function buildSignedTransaction({toAddress,toPubkeyHash,amountUnits,feeUnits,privkeyHex,seedPhrase,utxos,dustUnits=546}){
    if(!privkeyHex && seedPhrase) privkeyHex = await privkeyFromSeedPhrase(seedPhrase);
    const priv=hexToBytes(privkeyHex);
    const pub=getPublicKey(priv,true);
    const myPkh=bytesToHex(await hash160(pub));
    const toPkh=toPubkeyHash||pubkeyHashFromAddress(toAddress);

    const target=amountUnits+feeUnits;
    const {chosen,total}=selectUTXOs(utxos,target);
    if(total<target) throw new Error('Not enough balance (need '+(target)+', have '+total+')');

    const outputs=[{value:amountUnits,pkh:toPkh}];
    const change=total-target;
    if(change>=dustUnits) outputs.push({value:change,pkh:myPkh});

    // --- BIP143 shared hashes ---
    const prevouts=concat(...chosen.map(u=>concat(revHex(u.txid),u32le(u.vout))));
    const sequences=concat(...chosen.map(()=>u32le(0xffffffff)));
    const outsSer=concat(...outputs.map(o=>concat(u64le(o.value),varint(spkFromPubkeyHash(o.pkh).length),spkFromPubkeyHash(o.pkh))));
    const hashPrevouts=await dsha256(prevouts);
    const hashSequence=await dsha256(sequences);
    const hashOutputs=await dsha256(outsSer);
    const version=u32le(2), locktime=u32le(0), sighashType=u32le(1);
    const sc=scriptCode(myPkh);

    const witnesses=[];
    for(const u of chosen){
        const outpoint=concat(revHex(u.txid),u32le(u.vout));
        const preimage=concat(version,hashPrevouts,hashSequence,outpoint,
            sc,u64le(u.value),u32le(0xffffffff),hashOutputs,locktime,sighashType);
        const sighash=await dsha256(preimage);
        let sig=await signAsync(sighash,priv); sig=sig.normalizeS();
        const der=concat(derSig(sig.r,sig.s),new Uint8Array([0x01]));
        witnesses.push([der,pub]);
    }

    // --- serialize (segwit) ---
    const vin=concat(...chosen.map(u=>concat(revHex(u.txid),u32le(u.vout),new Uint8Array([0x00]),u32le(0xffffffff))));
    const vout=concat(varint(outputs.length),outsSer);
    const witSer=concat(...witnesses.map(w=>concat(varint(w.length),...w.map(item=>concat(varint(item.length),item)))));
    const raw=concat(version,new Uint8Array([0x00,0x01]),varint(chosen.length),vin,vout,witSer,locktime);
    // txid = dsha256 of the non-witness serialization, reversed
    const nonwit=concat(version,varint(chosen.length),vin,vout,locktime);
    const txid=bytesToHex((await dsha256(nonwit)).reverse());
    return {rawHex:bytesToHex(raw),txid,fee:feeUnits,change};
}
