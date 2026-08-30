# Vendored third-party code

## noble-secp256k1.js

- Package: `@noble/secp256k1`
- Version: 2.1.0
- Source: `npm pack @noble/secp256k1@2.1.0`, file `package/index.js`, copied byte-for-byte
- Tarball SHA-256: `ad60ef4a38fb7eb83111c74de4a2be13dd5d001db50431f3710b5ae0cb0ad3e6`
- License: MIT (see `noble-secp256k1.LICENSE`)

Vendored rather than loaded from a CDN so the wallet keeps working offline as
a PWA and so no third party can alter the code that touches private keys.

Used only to derive a public key from the seed-derived private scalar. The
private key never leaves the browser.

To update: re-run `npm pack`, diff the new `index.js`, and re-run
`tests/test_address_derivation.py`, which cross-checks the JS derivation
against the Python chain code.
