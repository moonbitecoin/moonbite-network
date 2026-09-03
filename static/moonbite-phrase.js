/* MoonBite recovery phrases — standard BIP39 (12 words, 128-bit, checksummed).
 * Thin wrapper over moonbite-bip39.js so existing callers keep working. */
import { generateMnemonic, validateMnemonic, wordlistSize, wordMatches, normalize }
    from './moonbite-bip39.js';

/* A fresh 12-word phrase. Async: uses WebCrypto. */
export async function generatePhrase() { return generateMnemonic(128); }
export { validateMnemonic, wordlistSize, wordMatches, normalize };
