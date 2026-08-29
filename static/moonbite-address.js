/* MoonBite address derivation — browser side.
 *
 * A direct port of wallet.py's derive_from_seed_phrase(). The user's seed
 * phrase never leaves the device: the private key, public key and address are
 * all computed here, and only the finished address is ever sent to the server
 * (to read a public balance).
 *
 * Both implementations must agree byte-for-byte or a user's funds would land
 * at an address their other device cannot see, so
 * tests/test_address_derivation.py runs this file under node and asserts the
 * addresses match Python's for a spread of phrases. Change the scheme here and
 * that test fails.
 */
import { getPublicKey } from './vendor/noble-secp256k1.js';

const SEED_DERIVATION_PREFIX = 'moonbite-seed-v1:';
const BECH32_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';
const MOONBITE_HRP = 'moon';

// secp256k1 group order — a raw SHA-256 digest can exceed it, and anything
// >= n is not a valid private scalar.
const CURVE_ORDER =
    0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141n;

/* Case and whitespace runs carry no meaning in a written phrase, and a user
   retyping their seed on a second device will not reproduce them exactly.
   Normalize formatting only — never content. */
export function normalizeSeedPhrase(phrase) {
    return String(phrase).trim().toLowerCase().split(/\s+/).join(' ');
}

function bytesToHex(bytes) {
    let out = '';
    for (const b of bytes) out += b.toString(16).padStart(2, '0');
    return out;
}

function hexToBytes(hex) {
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i++) {
        out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    }
    return out;
}

async function sha256(bytes) {
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return new Uint8Array(digest);
}

function bech32Polymod(values) {
    const generator = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];
    let chk = 1;
    for (const value of values) {
        const top = chk >>> 25;
        chk = ((chk & 0x1ffffff) << 5) ^ value;
        for (let i = 0; i < 5; i++) {
            if ((top >>> i) & 1) chk ^= generator[i];
        }
    }
    // Force unsigned: the shifts above can push the sign bit in 32-bit ints.
    return chk >>> 0;
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
    for (let i = 0; i < 6; i++) out.push((polymod >>> (5 * (5 - i))) & 31);
    return out;
}

function bech32Encode(hrp, data) {
    const combined = data.concat(bech32CreateChecksum(hrp, data));
    let out = hrp + '1';
    for (const d of combined) out += BECH32_CHARSET[d];
    return out;
}

/* Regroup a bit-stream between 8-bit bytes and 5-bit bech32 symbols. */
function convertBits(data, fromBits, toBits, pad) {
    let acc = 0;
    let bits = 0;
    const ret = [];
    const maxv = (1 << toBits) - 1;
    for (const value of data) {
        if (value < 0 || value >> fromBits !== 0) return null;
        acc = (acc << fromBits) | value;
        bits += fromBits;
        while (bits >= toBits) {
            bits -= toBits;
            ret.push((acc >> bits) & maxv);
        }
    }
    if (pad) {
        if (bits > 0) ret.push((acc << (toBits - bits)) & maxv);
    } else if (bits >= fromBits || ((acc << (toBits - bits)) & maxv)) {
        return null;
    }
    return ret;
}

export function addressFromPubkeyHash(pkhHex, hrp = MOONBITE_HRP) {
    const data = convertBits(hexToBytes(pkhHex), 8, 5, true);
    if (data === null) throw new Error('cannot encode pubkey hash');
    return bech32Encode(hrp, data);
}

export async function privkeyFromSeedPhrase(phrase) {
    const normalized = normalizeSeedPhrase(phrase);
    if (!normalized) throw new Error('seed phrase is empty');
    const material = new TextEncoder().encode(SEED_DERIVATION_PREFIX + normalized);
    const digest = await sha256(material);
    const scalar = BigInt('0x' + bytesToHex(digest)) % CURVE_ORDER;
    if (scalar === 0n) throw new Error('degenerate key for this seed phrase');
    return scalar.toString(16).padStart(64, '0');
}

/* Full derivation: seed phrase -> private key, public key, hash, address. */
export async function deriveFromSeedPhrase(phrase) {
    const privkeyHex = await privkeyFromSeedPhrase(phrase);
    // Uncompressed gives 65 bytes with a leading 0x04 tag; the chain hashes
    // the raw X||Y that python-ecdsa's to_string() produces, so drop the tag.
    const uncompressed = getPublicKey(hexToBytes(privkeyHex), false);
    const pubkeyHex = bytesToHex(uncompressed.slice(1));
    const pkhHex = bytesToHex(await sha256(hexToBytes(pubkeyHex)));
    return {
        private_key: privkeyHex,
        public_key: pubkeyHex,
        pubkey_hash: pkhHex,
        address: addressFromPubkeyHash(pkhHex)
    };
}
