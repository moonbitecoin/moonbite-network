/* Seed-phrase encryption for the MoonBite wallet.
 *
 * This replaces a scheme that provided no protection at all. It XORed the seed
 * against simpleHash(pin), a function that pads 56 leading zeros and puts its
 * entropy in the last 8 characters. A seed phrase is shorter than that padding,
 * so the keystream was the literal character '0' for every PIN — the stored
 * seed was plaintext XOR 0x30, readable with no PIN whatsoever.
 *
 * What replaces it:
 *
 *   PBKDF2-HMAC-SHA256, 310,000 iterations, fresh 16-byte salt per wallet,
 *   then AES-256-GCM with a fresh 12-byte IV.
 *
 * GCM authenticates as well as encrypts, which is what lets the wallet stop
 * storing the PIN: a wrong PIN makes decryption *fail* rather than return
 * plausible garbage, so the PIN can be checked by trying it. The previous
 * build kept the PIN in localStorage in the clear, beside the seed it was
 * meant to protect.
 *
 * Honest limit: a 6-digit PIN is a million possibilities. The iteration count
 * makes each guess cost real time, which is what stops casual offline
 * cracking, but it is not a defence against someone determined who has copied
 * the stored blob. The seed phrase — not the PIN — is the actual secret, and a
 * longer passphrase would be materially stronger here.
 */

const PBKDF2_ITERATIONS = 310000;   // OWASP guidance for PBKDF2-HMAC-SHA256
const SALT_BYTES = 16;
const IV_BYTES = 12;                // 96 bits, the size GCM is defined for
const VERSION = 'mb1';

const enc = new TextEncoder();
const dec = new TextDecoder();

function toBase64(bytes) {
    let s = '';
    for (const b of bytes) s += String.fromCharCode(b);
    return btoa(s);
}

function fromBase64(b64) {
    const s = atob(b64);
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out;
}

async function deriveKey(pin, salt) {
    const material = await crypto.subtle.importKey(
        'raw', enc.encode(String(pin)), 'PBKDF2', false, ['deriveKey']
    );
    return crypto.subtle.deriveKey(
        { name: 'PBKDF2', salt, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' },
        material,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
    );
}

/* Envelope: mb1.<salt>.<iv>.<ciphertext>, each base64.
   The version prefix is what lets the wallet recognise an old blob and
   migrate it instead of failing to read it. */
export async function encryptSeed(seedPhrase, pin) {
    if (!seedPhrase) throw new Error('nothing to encrypt');
    const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
    const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
    const key = await deriveKey(pin, salt);
    const ct = new Uint8Array(await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv }, key, enc.encode(seedPhrase)
    ));
    return [VERSION, toBase64(salt), toBase64(iv), toBase64(ct)].join('.');
}

/* Returns the seed, or null if the PIN is wrong.

   Null rather than an exception because every caller asks the same question —
   "is this the right PIN?" — and GCM's authentication failure is the answer,
   not an error condition to report. */
export async function decryptSeed(envelope, pin) {
    if (!isNewFormat(envelope)) throw new Error('not a versioned envelope');
    const [, saltB64, ivB64, ctB64] = envelope.split('.');
    try {
        const key = await deriveKey(pin, fromBase64(saltB64));
        const pt = await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: fromBase64(ivB64) }, key, fromBase64(ctB64)
        );
        return dec.decode(pt);
    } catch (e) {
        return null;   // authentication failed: wrong PIN, or tampered blob
    }
}

export function isNewFormat(envelope) {
    return typeof envelope === 'string' && envelope.startsWith(VERSION + '.');
}

/* Read a blob written by the broken scheme.
 *
 * Kept only so existing wallets can be migrated on the next unlock. It takes
 * no PIN because the original never really used one: recovering the seed is
 * XOR with '0'. That is precisely the flaw, and the reason every stored seed
 * written before this change should be treated as already exposed. */
export function decryptLegacy(stored) {
    try {
        const decoded = atob(stored);
        let out = '';
        for (let i = 0; i < decoded.length; i++) {
            out += String.fromCharCode(decoded.charCodeAt(i) ^ 0x30);
        }
        return out;
    } catch (e) {
        return null;
    }
}

/* One call for the unlock path: read a seed in either format.

   Returns { seed, migrated }. `migrated` is true when the blob was in the old
   format, telling the caller to re-encrypt and overwrite it. */
export async function readSeed(stored, pin) {
    if (isNewFormat(stored)) {
        return { seed: await decryptSeed(stored, pin), migrated: false };
    }
    return { seed: decryptLegacy(stored), migrated: true };
}
