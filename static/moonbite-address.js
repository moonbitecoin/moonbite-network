/* MoonBite address derivation — standard native segwit (P2WPKH), matching
 * MoonBite Core exactly: address = bech32("moon", 0, RIPEMD160(SHA256(pubkey)))
 * with the COMPRESSED public key. Verified against the node's wpkh descriptor.
 *
 * New wallets use BIP39 (12 words) -> BIP84 m/84'/2'/0'/0/0. A phrase that is
 * not valid BIP39 (an older imported phrase) still yields a real P2WPKH
 * address via a legacy scalar derivation, so nothing is stranded.
 */
import { getPublicKey } from './vendor/noble-secp256k1.js?v=20260904a';
import { mnemonicToSeed, validateMnemonic } from './moonbite-bip39.js?v=20260904a';
import { deriveKey, hash160, bytesToHex, hexToBytes } from './moonbite-hd.js?v=20260904a';

const SEED_DERIVATION_PREFIX = 'moonbite-seed-v1:';
const BECH32_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';
const MOONBITE_HRP = 'moon';
const WITVER = 0;
const CURVE_ORDER =
    BigInt('0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141');

export function normalizeSeedPhrase(phrase) {
    return (phrase || '').normalize('NFKD').trim().replace(/\s+/g, ' ').toLowerCase();
}
async function sha256(bytes) { return new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)); }

function bech32Polymod(values) {
    const GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];
    let chk = 1;
    for (const v of values) {
        const b = chk >> 25;
        chk = ((chk & 0x1ffffff) << 5) ^ v;
        for (let i = 0; i < 5; i++) if ((b >> i) & 1) chk ^= GEN[i];
    }
    return chk;
}
function bech32HrpExpand(hrp) {
    const out = [];
    for (const c of hrp) out.push(c.charCodeAt(0) >> 5);
    out.push(0);
    for (const c of hrp) out.push(c.charCodeAt(0) & 31);
    return out;
}
function bech32CreateChecksum(hrp, data) {
    const values = bech32HrpExpand(hrp).concat(data, [0, 0, 0, 0, 0, 0]);
    const polymod = bech32Polymod(values) ^ 1;
    const out = [];
    for (let i = 0; i < 6; i++) out.push((polymod >> (5 * (5 - i))) & 31);
    return out;
}
function bech32Encode(hrp, data) {
    const combined = data.concat(bech32CreateChecksum(hrp, data));
    let s = hrp + '1';
    for (const d of combined) s += BECH32_CHARSET[d];
    return s;
}
function bech32Decode(addr) {
    addr = addr.toLowerCase();
    const pos = addr.lastIndexOf('1');
    const hrp = addr.slice(0, pos);
    const data = [];
    for (const c of addr.slice(pos + 1)) {
        const d = BECH32_CHARSET.indexOf(c);
        if (d < 0) throw new Error('invalid bech32 char');
        data.push(d);
    }
    if (bech32Polymod(bech32HrpExpand(hrp).concat(data)) !== 1) throw new Error('bad checksum');
    return { hrp, data: data.slice(0, -6) };
}
function convertBits(data, fromBits, toBits, pad) {
    let acc = 0, bits = 0;
    const out = [];
    const maxv = (1 << toBits) - 1;
    for (const value of data) {
        acc = (acc << fromBits) | value;
        bits += fromBits;
        while (bits >= toBits) { bits -= toBits; out.push((acc >> bits) & maxv); }
    }
    if (pad) { if (bits) out.push((acc << (toBits - bits)) & maxv); }
    else if (bits >= fromBits || ((acc << (toBits - bits)) & maxv)) return null;
    return out;
}

/* 20-byte pubkey-hash (hex) -> moon1 P2WPKH address. */
export function addressFromPubkeyHash(pkhHex, hrp = MOONBITE_HRP) {
    const prog = convertBits(hexToBytes(pkhHex), 8, 5, true);
    if (prog === null) throw new Error('cannot encode pubkey hash');
    return bech32Encode(hrp, [WITVER].concat(prog));
}
/* moon1 address -> 20-byte pubkey-hash (hex). */
export function pubkeyHashFromAddress(addr) {
    const { hrp, data } = bech32Decode(addr);
    if (hrp !== MOONBITE_HRP) throw new Error('not a MoonBite address');
    if (data[0] !== WITVER) throw new Error('unsupported witness version');
    const prog = convertBits(data.slice(1), 5, 8, false);
    if (prog === null || prog.length !== 20) throw new Error('bad program length');
    return bytesToHex(new Uint8Array(prog));
}
export function isValidAddress(addr) {
    try { pubkeyHashFromAddress(addr); return true; } catch (e) { return false; }
}

/* Private key (hex) for a phrase: BIP84 for valid BIP39, else legacy scalar. */
export async function privkeyFromSeedPhrase(phrase) {
    const normalized = normalizeSeedPhrase(phrase);
    if (!normalized) throw new Error('seed phrase is empty');
    if (await validateMnemonic(normalized)) {
        const seed = await mnemonicToSeed(normalized);
        return (await deriveKey(seed, 0)).privkey;
    }
    const material = new TextEncoder().encode(SEED_DERIVATION_PREFIX + normalized);
    const digest = await sha256(material);
    const scalar = BigInt('0x' + bytesToHex(digest)) % CURVE_ORDER;
    if (scalar === 0n) throw new Error('degenerate key for this seed phrase');
    return scalar.toString(16).padStart(64, '0');
}

/* Full derivation -> { private_key, public_key(compressed), pubkey_hash, address }. */
export async function deriveFromSeedPhrase(phrase) {
    const privkeyHex = await privkeyFromSeedPhrase(phrase);
    const compressed = getPublicKey(hexToBytes(privkeyHex), true);
    const pubkeyHex = bytesToHex(compressed);
    const pkhHex = bytesToHex(await hash160(compressed));
    return {
        private_key: privkeyHex,
        public_key: pubkeyHex,
        pubkey_hash: pkhHex,
        address: addressFromPubkeyHash(pkhHex),
    };
}
