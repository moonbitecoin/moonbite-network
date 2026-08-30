/* Secure recovery-phrase generation for "Create a new wallet".
 *
 * The wallet's derivation is free-form — it hashes the normalized phrase
 * string — so a phrase only needs to be high-entropy and reproducible from
 * what the user writes down. This generates a 9-word phrase from a curated
 * list of common, distinct, easily-written words using crypto.getRandomValues
 * with rejection sampling (no modulo bias).
 *
 * The old static/bip39.js shipped a corrupted "wordlist" full of duplicates
 * and medical jargon; it is not used.
 *
 * Entropy: 9 words drawn from this list. With ~240 usable words that is
 * ~9 * log2(240) ≈ 71 bits. Adequate for this chain, and a user who wants
 * more can supply their own longer phrase through Import instead.
 */

// Curated for legibility: short, common, unambiguous words, no near-homophones.
const WORDS = Array.from(new Set([
    'anchor','apple','arctic','arrow','autumn','amber','apron','arena',
    'basket','beacon','bison','bloom','bolt','bounce','bridge','bronze','buffalo','bundle',
    'cabin','cactus','candle','canyon','carbon','castle','cedar','cherry','clever','cloud','clover','cobra','copper','coral','cotton','crane','crimson','crystal','current',
    'dagger','daisy','dawn','delta','denim','desert','diamond','dolphin','dragon','drift','dune','dusk',
    'eagle','ember','emerald','engine','ember','ethereal','ember','echo','edge','elder','ember',
    'fabric','falcon','fern','fiber','fjord','flame','flint','forest','fossil','fox','frost','fusion',
    'galaxy','garden','glacier','glide','granite','grove','gully','guitar',
    'hammer','harbor','hawk','hazel','hollow','honey','horizon','hunter',
    'igloo','indigo','ingot','iris','island','ivory',
    'jacket','jaguar','jasmine','jetty','jewel','jungle','juniper',
    'kayak','kernel','kettle','keystone','kingdom','kitten','koala',
    'ladder','lagoon','lantern','laurel','ledger','lemon','lily','linen','lizard','lotus','lunar','lynx',
    'magnet','maple','marble','meadow','meteor','mint','mirror','mist','mohawk','moss','mountain','mulberry',
    'nebula','nectar','needle','nickel','nomad','north','nova','nugget',
    'oasis','ocean','olive','onyx','opal','orbit','orchid','otter','oxygen',
    'paddle','palace','panda','parcel','pebble','pepper','pewter','pigeon','pillar','pine','pixel','plasma','plum','pocket','pollen','portal','prairie','prism','pueblo','pumpkin',
    'quartz','quill','quilt','quiver',
    'radar','radish','rainbow','ranch','raven','reef','ribbon','ridge','ripple','river','robin','rocket','rooster','ruby','rustic',
    'saffron','sailor','salmon','sapphire','satin','scarlet','sequoia','shadow','shell','silk','silver','sketch','slate','sleek','solar','sparrow','spruce','stallion','stellar','stone','storm','summit','sunset','swift',
    'talon','tandem','teak','temple','thicket','thunder','timber','topaz','torch','totem','trail','tulip','tundra','turquoise','turtle',
    'umber','umbra','unicorn','uplift','urban',
    'valley','velvet','venom','vertex','violet','viper','vista','volcano','voyage',
    'walnut','walrus','wander','wasp','willow','window','winter','wombat','wonder','woven',
    'yarrow','yellow','yeti','yonder',
    'zebra','zenith','zephyr','zinnia'
]));

/* Pick an index in [0, max) uniformly, discarding biased draws. */
function unbiasedIndex(max) {
    const limit = Math.floor(0x100000000 / max) * max;
    const buf = new Uint32Array(1);
    let x;
    do { crypto.getRandomValues(buf); x = buf[0]; } while (x >= limit);
    return x % max;
}

/* Generate an n-word (default 9) recovery phrase. */
export function generatePhrase(n = 9) {
    const words = [];
    for (let i = 0; i < n; i++) {
        words.push(WORDS[unbiasedIndex(WORDS.length)]);
    }
    return words.join(' ');
}

export function wordlistSize() {
    return WORDS.length;
}
