import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'package:moonbite_mobile/services/chain_service.dart';
import 'package:moonbite_mobile/wallet/authenticator.dart';
import 'package:moonbite_mobile/wallet/moonbite_network.dart';
import 'package:moonbite_mobile/wallet/secure_key_store.dart';
import 'package:moonbite_mobile/wallet/tx_builder.dart';
import 'package:moonbite_mobile/wallet/wallet_controller.dart';

/// Deterministic stand-in for the biometric gate. [approve] decides whether a
/// spend is allowed; [calls] records every reason string it was asked with so
/// tests can assert the gate ran (or didn't) exactly when expected.
class _FakeAuthenticator implements Authenticator {
  _FakeAuthenticator(this.approve);
  final bool approve;
  final List<String> calls = [];
  @override
  Future<bool> authenticate(String reason) async {
    calls.add(reason);
    return approve;
  }
}

const _mnemonic =
    'abandon abandon abandon abandon abandon abandon '
    'abandon abandon abandon abandon abandon about';
// index-0 testnet address for the vector above, and its scriptPubKey.
const _addr0 = 'tbig1q6rz28mcfaxtmd6v789l9rrlrusdprr9pdc24tr';
const _spk0 = '0014d0c4a3ef09e997b6e99e397e518fe3e41a118ca1';
const _dest = 'tbig1qd7spv5q28348xl4myc8zmh983w5jx32clha2cz';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late String? lastBroadcastHex;

  http.Client fakeHttp() => MockClient((req) async {
        final path = req.url.path;
        if (path.endsWith('/api/status')) {
          return http.Response(
              jsonEncode({
                'chain': 'test',
                'blocks': 50,
                'headers': 50,
                'bestblockhash': 'abc',
                'difficulty': 1.0,
                'verificationprogress': 1.0,
                'mempool_txs': 0,
                'connections': 3,
                'subversion': '/MoonBite:2.5.0/',
                'demo': false,
              }),
              200);
        }
        if (path.contains('/balance')) {
          return http.Response(
              jsonEncode({
                'address': _addr0,
                'confirmed': 50.0,
                'unconfirmed': 0.0,
                'total': 50.0,
                'utxo_count': 1,
                'demo': false,
              }),
              200);
        }
        if (path.contains('/utxos')) {
          return http.Response(
              jsonEncode({
                'address': _addr0,
                'utxos': [
                  {
                    'txid':
                        '1111111111111111111111111111111111111111111111111111111111111111',
                    'vout': 0,
                    'amount': 50.0,
                    'scriptPubKey': _spk0,
                    'height': 10,
                    'confirmations': 120,
                  }
                ],
                'scan_height': 130,
                'demo': false,
              }),
              200);
        }
        if (path.endsWith('/api/fee')) {
          return http.Response(
              jsonEncode({'feerate': 0.00001, 'blocks': 6, 'source': 'x'}),
              200);
        }
        if (path.endsWith('/api/tx/broadcast')) {
          lastBroadcastHex =
              (jsonDecode(req.body) as Map<String, dynamic>)['rawtx'] as String;
          // Model a node that accepts but echoes no txid; the controller must
          // then return its own locally-computed txid.
          return http.Response(jsonEncode({'txid': ''}), 200);
        }
        return http.Response('{"error":"unexpected ${req.url}"}', 404);
      });

  WalletController makeController({Authenticator? auth}) => WalletController(
        chain: ChainService(baseUrl: 'https://x', httpClient: fakeHttp()),
        store: SecureKeyStore(),
        authenticator: auth ?? _FakeAuthenticator(true),
      );

  setUp(() {
    lastBroadcastHex = null;
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('imports a wallet and derives the index-0 address', () async {
    final c = makeController();
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    expect(c.hasWallet, isTrue);
    expect(c.receiveAddress, _addr0);
    expect(await c.store.hasWallet(), isTrue);
  });

  test('createNew persists and produces a tbig1 address', () async {
    final c = makeController();
    final phrase = await c.createNew(network: MoonBiteNetwork.testnet);
    expect(phrase.split(' ').length, 12);
    expect(c.receiveAddress.startsWith('tbig1'), isTrue);

    // A fresh controller should load the same wallet back from storage.
    final c2 = makeController();
    expect(await c2.loadExisting(), isTrue);
    expect(c2.receiveAddress, c.receiveAddress);
  });

  test('refresh loads status and balance', () async {
    final c = makeController();
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    await c.refresh();
    expect(c.status?.chain, 'test');
    expect(c.balance?.total, 50.0);
    expect(c.error, isNull);
  });

  test('send builds, signs, and returns the locally-computed txid', () async {
    final c = makeController();
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    final txid = await c.send(toAddress: _dest, amountBig: 1.0);
    // We return OUR txid (64-hex), not whatever the relay claimed.
    expect(txid, matches(RegExp(r'^[0-9a-f]{64}$')));
    // The broadcast payload must be a real signed tx hex (segwit marker 0001).
    expect(lastBroadcastHex, isNotNull);
    expect(lastBroadcastHex!.startsWith('02000000'), isTrue);
    expect(lastBroadcastHex!.contains('0001'), isTrue);
  });

  test('send rejects a relay that returns a mismatched txid', () async {
    // A malicious relay claims a different txid than the one we signed.
    final c = WalletController(
      chain: ChainService(
        baseUrl: 'https://x',
        httpClient: MockClient((req) async {
          final path = req.url.path;
          if (path.contains('/utxos')) {
            return http.Response(
                jsonEncode({
                  'utxos': [
                    {
                      'txid':
                          '1111111111111111111111111111111111111111111111111111111111111111',
                      'vout': 0,
                      'amount': 50.0,
                      'scriptPubKey': _spk0,
                      'height': 10,
                      'confirmations': 120,
                    }
                  ],
                }),
                200);
          }
          if (path.endsWith('/api/fee')) {
            return http.Response(jsonEncode({'feerate': 0.00001}), 200);
          }
          if (path.endsWith('/api/tx/broadcast')) {
            return http.Response(
                jsonEncode({'txid': 'a' * 64}), 200); // bogus, != ours
          }
          return http.Response('{}', 200);
        }),
      ),
      store: SecureKeyStore(),
      authenticator: _FakeAuthenticator(true),
    );
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    await expectLater(
      c.send(toAddress: _dest, amountBig: 1.0),
      throwsA(isA<StateError>()),
    );
  });

  test('send aborts before broadcast when authentication is denied', () async {
    final denier = _FakeAuthenticator(false);
    final c = makeController(auth: denier);
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    await expectLater(
      c.send(toAddress: _dest, amountBig: 1.0),
      throwsA(isA<AuthenticationException>()),
    );
    // The gate was consulted, and nothing was signed or broadcast.
    expect(denier.calls, hasLength(1));
    expect(lastBroadcastHex, isNull);
  });

  test('send proceeds and broadcasts when authentication is approved',
      () async {
    final approver = _FakeAuthenticator(true);
    final c = makeController(auth: approver);
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    final txid = await c.send(toAddress: _dest, amountBig: 1.0);
    expect(approver.calls, hasLength(1));
    expect(txid, matches(RegExp(r'^[0-9a-f]{64}$')));
    expect(lastBroadcastHex, isNotNull);
  });

  test('previewSpend reports the fee without broadcasting', () async {
    final c = makeController();
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    final preview = await c.previewSpend(toAddress: _dest, amountBig: 1.0);
    expect(preview.feeSats, greaterThan(0));
    expect(preview.amountSats, 100000000);
    // A preview must never hit the broadcast endpoint.
    expect(lastBroadcastHex, isNull);
  });

  test('send refuses an implausibly high node-quoted fee rate', () async {
    // A hostile node quotes an absurd fee rate; the wallet must refuse rather
    // than burn the UTXO as fee. Auth is approved so we prove the fee cap —
    // not the auth gate — is what stops the send.
    final c = WalletController(
      chain: ChainService(
        baseUrl: 'https://x',
        httpClient: MockClient((req) async {
          final path = req.url.path;
          if (path.contains('/utxos')) {
            return http.Response(
                jsonEncode({
                  'utxos': [
                    {
                      'txid':
                          '1111111111111111111111111111111111111111111111111111111111111111',
                      'vout': 0,
                      'amount': 50.0,
                      'scriptPubKey': _spk0,
                      'height': 10,
                      'confirmations': 120,
                    }
                  ],
                }),
                200);
          }
          if (path.endsWith('/api/fee')) {
            // 1.0 BIG/kB => 100000 sat/vB, far above the safety cap.
            return http.Response(jsonEncode({'feerate': 1.0}), 200);
          }
          return http.Response('{}', 200);
        }),
      ),
      store: SecureKeyStore(),
      authenticator: _FakeAuthenticator(true),
    );
    await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
    await expectLater(
      c.send(toAddress: _dest, amountBig: 1.0),
      throwsA(isA<ExcessiveFeeRateException>()),
    );
  });

  test('rejects an invalid mnemonic import', () async {
    final c = makeController();
    expect(
      () => c.importExisting('not a valid phrase'),
      throwsArgumentError,
    );
  });

  group('app-open lock', () {
    test('a wallet restored from storage starts locked', () async {
      // Seed storage via one controller, then load it in a fresh one.
      final seed = makeController();
      await seed.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);

      final c = makeController();
      expect(await c.loadExisting(), isTrue);
      expect(c.hasWallet, isTrue);
      expect(c.requiresUnlock, isTrue,
          reason: 'a restored wallet must require a fresh unlock');
    });

    test('createNew and importExisting start unlocked (active onboarding)',
        () async {
      final created = makeController();
      await created.createNew(network: MoonBiteNetwork.testnet);
      expect(created.requiresUnlock, isFalse);

      final imported = makeController();
      await imported.importExisting(_mnemonic,
          network: MoonBiteNetwork.testnet);
      expect(imported.requiresUnlock, isFalse);
    });

    test('unlock clears the gate when authentication is approved', () async {
      final seed = makeController();
      await seed.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);

      final approver = _FakeAuthenticator(true);
      final c = makeController(auth: approver);
      await c.loadExisting();
      expect(c.requiresUnlock, isTrue);

      final ok = await c.unlock();
      expect(ok, isTrue);
      expect(c.requiresUnlock, isFalse);
      expect(approver.calls, hasLength(1));
      expect(approver.calls.single, contains('Unlock'));
    });

    test('unlock keeps the wallet locked when authentication is denied',
        () async {
      final seed = makeController();
      await seed.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);

      final denier = _FakeAuthenticator(false);
      final c = makeController(auth: denier);
      await c.loadExisting();

      final ok = await c.unlock();
      expect(ok, isFalse);
      expect(c.requiresUnlock, isTrue);
      expect(denier.calls, hasLength(1));
    });

    test('lock re-engages the gate after a successful unlock', () async {
      final c = makeController();
      await c.importExisting(_mnemonic, network: MoonBiteNetwork.testnet);
      expect(c.requiresUnlock, isFalse);

      c.lock();
      expect(c.requiresUnlock, isTrue,
          reason: 'backgrounding must re-lock a stored wallet');
    });
  });
}
