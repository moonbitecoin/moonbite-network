import 'package:flutter/foundation.dart';

import '../models/chain_models.dart';
import '../services/chain_service.dart';
import 'authenticator.dart';
import 'moonbite_network.dart';
import 'hd_wallet_service.dart';
import 'secure_key_store.dart';
import 'tx_builder.dart';

/// Orchestrates the non-custodial wallet: key storage, derivation, balance
/// refresh, and on-device signing + broadcast. UI observes this via Provider.
///
/// A single external receive address (BIP84 index 0) is used; change returns
/// to the same address. Keys never leave the device — [ChainService] only
/// fetches chain state and relays already-signed transactions.
class WalletController extends ChangeNotifier {
  final ChainService chain;
  final SecureKeyStore store;
  final Authenticator authenticator;

  WalletController({
    required this.chain,
    SecureKeyStore? store,
    Authenticator? authenticator,
  })  : store = store ?? SecureKeyStore(),
        authenticator = authenticator ?? LocalAuthenticator();

  MoonBiteNetwork _network = MoonBiteNetwork.testnet;
  String? _mnemonic;
  MoonBiteAccount? _account;
  WalletBalance? _balance;
  ChainStatus? _status;
  bool _busy = false;
  String? _error;
  bool _unlocked = false;

  MoonBiteNetwork get network => _network;
  MoonBiteAccount? get account => _account;
  WalletBalance? get balance => _balance;
  ChainStatus? get status => _status;
  bool get busy => _busy;
  String? get error => _error;
  bool get hasWallet => _account != null;

  /// True when a wallet exists on the device but the owner has not proven
  /// presence yet this session. The UI must show a lock gate and refuse to
  /// display balances / addresses until [unlock] succeeds.
  bool get requiresUnlock => hasWallet && !_unlocked;

  String get receiveAddress => _account?.bech32Address ?? '';

  HdWalletService get _hd => HdWalletService(_network);

  void _set({bool? busy, String? error, bool clearError = false}) {
    if (busy != null) _busy = busy;
    if (clearError) _error = null;
    if (error != null) _error = error;
    notifyListeners();
  }

  /// Loads a previously-created wallet from secure storage, if any.
  Future<bool> loadExisting() async {
    if (!await store.hasWallet()) return false;
    final mnemonic = await store.readMnemonic();
    final netId = await store.readNetworkId();
    if (mnemonic == null) return false;
    _network = MoonBiteNetwork.byId(netId);
    _mnemonic = mnemonic;
    _account = _hd.deriveAccount(mnemonic, index: 0);
    // A wallet restored from storage starts LOCKED: the owner must prove
    // presence (biometric / device PIN) before the app reveals it. This blocks
    // someone who picks up an already-unlocked phone from seeing balances or
    // the receive address.
    _unlocked = false;
    notifyListeners();
    return true;
  }

  /// Proves presence to reveal a stored wallet. Returns true on success; on
  /// failure or cancellation the wallet stays locked and the UI keeps the gate.
  Future<bool> unlock() async {
    if (_unlocked) return true;
    if (!hasWallet) return false;
    final ok = await authenticator.authenticate('Unlock your MoonBite wallet');
    if (ok) {
      _unlocked = true;
      notifyListeners();
    }
    return ok;
  }

  /// Re-engages the lock (e.g. when the app is backgrounded). The next reveal
  /// requires [unlock] again.
  void lock() {
    if (!_unlocked) return;
    _unlocked = false;
    notifyListeners();
  }

  /// Creates a brand-new wallet on [network] and persists it.
  Future<String> createNew({
    MoonBiteNetwork? network,
    int strengthBits = 128,
  }) async {
    _network = network ?? _network;
    final mnemonic = _hd.generateMnemonic(strengthBits: strengthBits);
    await _persistAndDerive(mnemonic);
    return mnemonic;
  }

  /// Imports an existing BIP39 mnemonic. Throws [ArgumentError] if invalid.
  Future<void> importExisting(String mnemonic, {MoonBiteNetwork? network}) async {
    _network = network ?? _network;
    final normalized = mnemonic.trim();
    if (!_hd.validateMnemonic(normalized)) {
      throw ArgumentError('Invalid recovery phrase');
    }
    await _persistAndDerive(normalized);
  }

  Future<void> _persistAndDerive(String mnemonic) async {
    await store.saveWallet(mnemonic: mnemonic, networkId: _network.id);
    _mnemonic = mnemonic;
    _account = _hd.deriveAccount(mnemonic, index: 0);
    // Just created/imported through the active onboarding flow, so the owner is
    // already present — start unlocked rather than immediately re-prompting.
    _unlocked = true;
    notifyListeners();
  }

  /// Refreshes chain status and this wallet's balance.
  Future<void> refresh() async {
    if (_account == null) return;
    _set(busy: true, clearError: true);
    try {
      final results = await Future.wait([
        chain.getStatus(),
        chain.getBalance(_account!.bech32Address),
      ]);
      _status = results[0] as ChainStatus;
      _balance = results[1] as WalletBalance;
    } catch (e) {
      _error = e.toString();
    } finally {
      _set(busy: false);
    }
  }

  /// Fetches UTXOs + the current fee rate and builds (and signs, on-device) the
  /// spend WITHOUT broadcasting it. Lets the UI show the exact fee and total
  /// before the user commits. Throws [ExcessiveFeeRateException] if the node's
  /// quoted fee rate is implausibly high, or [InsufficientFundsException].
  Future<SignedTx> previewSpend({
    required String toAddress,
    required double amountBig,
  }) async {
    final account = _account;
    if (account == null) {
      throw StateError('No wallet loaded');
    }
    final amountSats = (amountBig * 1e8).round();
    final utxos = await chain.getUtxos(account.bech32Address);
    final feeBigPerKb = await chain.getFeeRate();
    final feeSatPerVByte = feeBigPerKb * 1e8 / 1000;
    return TxBuilder(_network).buildSpend(
      utxos: utxos,
      toAddress: toAddress,
      amountSats: amountSats,
      changeAddress: account.bech32Address,
      wif: account.wif,
      feeRateSatPerVByte: feeSatPerVByte,
    );
  }

  /// Builds, signs (on-device), and broadcasts a payment of [amountBig] BIG to
  /// [toAddress]. Returns the accepted txid.
  Future<String> send({
    required String toAddress,
    required double amountBig,
  }) async {
    final account = _account;
    final mnemonic = _mnemonic;
    if (account == null || mnemonic == null) {
      throw StateError('No wallet loaded');
    }
    // Presence check BEFORE anything is built, signed, or broadcast. If the
    // device is unlocked and left unattended, this blocks an attacker from
    // draining funds without the owner's biometric/PIN.
    final ok = await authenticator.authenticate(
      'Authenticate to send ${amountBig.toStringAsFixed(8)} BIG',
    );
    if (!ok) {
      throw const AuthenticationException(
        'Authentication failed or was cancelled; the payment was not sent.',
      );
    }
    _set(busy: true, clearError: true);
    try {
      final signed = await previewSpend(
        toAddress: toAddress,
        amountBig: amountBig,
      );

      final relayTxid = await chain.broadcast(signed.rawHex);
      // Trust OUR locally-computed txid, never the relay's claim. A compromised
      // or malicious relay could report a bogus txid (fake "success" while
      // dropping the tx, or a value that doesn't match what we actually signed).
      // For a valid tx the node's txid must equal ours; a mismatch is a failure.
      if (relayTxid.isNotEmpty && relayTxid != signed.txid) {
        throw StateError(
          'Broadcast mismatch: relay returned "$relayTxid" but the signed '
          'transaction id is "${signed.txid}". Treating as failed.',
        );
      }
      await refresh();
      return signed.txid;
    } finally {
      _set(busy: false);
    }
  }

  /// Permanently removes the wallet from the device.
  Future<void> wipe() async {
    await store.wipe();
    _mnemonic = null;
    _account = null;
    _balance = null;
    _status = null;
    _unlocked = false;
    notifyListeners();
  }
}
