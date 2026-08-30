/* MoonBite transaction building and signing — browser side.
 *
 * The wallet holds the only copy of the key, so a spend is assembled and
 * signed here and only the finished, already-authorized transaction is sent to
 * the server. Nothing in this file transmits a seed or a private key.
 *
 * The signature covers a canonical JSON serialization that has to match
 * transaction.py's signing_bytes() byte for byte — a single differing space
 * would produce a signature the network rejects. tests/test_tx_signing.py runs
 * this file under node and checks both the exact bytes and that Python
 * accepts the resulting signatures.
 */
import { getPublicKey, signAsync } from './vendor/noble-secp256k1.js';
import { deriveFromSeedPhrase } from './moonbite-address.js';

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

/* Python's json.dumps(..., sort_keys=True, separators=(',', ':')).
 *
 * Not JSON.stringify: that preserves insertion order and would only agree by
 * luck. Keys are emitted in sorted order explicitly, and every value here is
 * an integer or a hex string, so no float or unicode escaping is involved. */
function canonicalJSON(value) {
    if (Array.isArray(value)) {
        return '[' + value.map(canonicalJSON).join(',') + ']';
    }
    if (value !== null && typeof value === 'object') {
        const keys = Object.keys(value).sort();
        return '{' + keys.map(k =>
            JSON.stringify(k) + ':' + canonicalJSON(value[k])).join(',') + '}';
    }
    if (typeof value === 'number' && !Number.isInteger(value)) {
        // Amounts are integer cents. A float here means a bug upstream, and
        // Python and JS do not agree on how to print one.
        throw new Error('non-integer number in transaction: ' + value);
    }
    return JSON.stringify(value);
}

/* The message every input signs (SIGHASH_ALL): the transaction with all
   signatures and pubkeys stripped, so a signature cannot be lifted onto a
   different transaction. */
export function signingBytes(tx) {
    const stripped = {
        inputs: tx.inputs.map(i => ({
            output_index: i.output_index,
            prev_txid: i.prev_txid
        })),
        outputs: tx.outputs.map(o => ({
            amount: o.amount,
            pubkey_hash: o.pubkey_hash
        }))
    };
    return new TextEncoder().encode(canonicalJSON(stripped));
}

async function sha256(bytes) {
    return new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
}

/* Choose which coins to spend.
 *
 * Largest-first, which keeps the input count (and so the signing work and the
 * transaction size) down. It leaks a little privacy by preferring big UTXOs,
 * but this chain has no fee market to optimize against and a wallet that
 * cannot build a spend at all is worse. */
export function selectUTXOs(utxos, target) {
    const sorted = [...utxos].sort((a, b) => b.amount_units - a.amount_units);
    const chosen = [];
    let total = 0;
    for (const u of sorted) {
        chosen.push(u);
        total += u.amount_units;
        if (total >= target) break;
    }
    if (total < target) {
        throw new Error('insufficient funds');
    }
    return { chosen, total };
}

/* Build and sign a spend.
 *
 * amountUnits and feeUnits are integer cents; change returns to the sender.
 * Change below dustUnits is dropped into the fee rather than creating an
 * output too small to be worth spending later. */
export async function buildSignedTransaction({
    seedPhrase,
    toPubkeyHash,
    amountUnits,
    feeUnits = 0,
    utxos,
    dustUnits = 1000
}) {
    if (!Number.isSafeInteger(amountUnits) || amountUnits <= 0) {
        throw new Error('amount must be a positive whole number of units');
    }
    if (!Number.isSafeInteger(feeUnits) || feeUnits < 0) {
        throw new Error('fee must be a non-negative whole number of units');
    }

    const key = await deriveFromSeedPhrase(seedPhrase);
    const { chosen, total } = selectUTXOs(utxos, amountUnits + feeUnits);

    const outputs = [{ amount: amountUnits, pubkey_hash: toPubkeyHash }];
    const change = total - amountUnits - feeUnits;
    if (change >= dustUnits) {
        outputs.push({ amount: change, pubkey_hash: key.pubkey_hash });
    }

    const tx = {
        inputs: chosen.map(u => ({
            prev_txid: u.txid,
            output_index: u.vout,
            pubkey: '',
            signature: ''
        })),
        outputs
    };

    // Every input commits to the same message, so hash it once.
    const digest = await sha256(signingBytes(tx));
    const privkey = hexToBytes(key.private_key);
    const pubkeyHex = bytesToHex(getPublicKey(privkey, false).slice(1));

    for (const input of tx.inputs) {
        const sig = await signAsync(digest, privkey);
        // Raw r||s, which is what python-ecdsa's verify() expects.
        input.signature = sig.toCompactHex();
        input.pubkey = pubkeyHex;
    }

    return {
        transaction: tx,
        // Reported so the UI can show what was actually spent rather than
        // what was requested — change and dust make those differ.
        inputsSpent: chosen.length,
        totalInputUnits: total,
        changeUnits: change >= dustUnits ? change : 0,
        feeUnits: change >= dustUnits ? feeUnits : feeUnits + change,
        fromAddress: key.address
    };
}
