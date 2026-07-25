// Dev/verification tool (not part of the app build).
//
// Reads a JSON job from stdin and prints the on-device-signed raw transaction,
// so an external moonbited can validate what the wallet produces.
//
// stdin JSON:
// {
//   "network": "testnet",
//   "mnemonic": "...",
//   "toAddress": "tbig1...",
//   "amountSats": 100000000,
//   "feeRateSatPerVByte": 1.0,
//   "utxos": [ { "txid","vout","amount","scriptPubKey","height","confirmations" } ]
// }
import 'dart:convert';
import 'dart:io';

import 'package:moonbite_mobile/models/chain_models.dart';
import 'package:moonbite_mobile/wallet/moonbite_network.dart';
import 'package:moonbite_mobile/wallet/hd_wallet_service.dart';
import 'package:moonbite_mobile/wallet/tx_builder.dart';

Future<void> main() async {
  final raw = await stdin.transform(utf8.decoder).join();
  final cfg = jsonDecode(raw) as Map<String, dynamic>;

  final net = MoonBiteNetwork.byId(cfg['network'] as String);
  final svc = HdWalletService(net);
  final acct0 = svc.deriveAccount(cfg['mnemonic'] as String, index: 0);

  final utxos = (cfg['utxos'] as List)
      .map((e) => Utxo.fromJson(e as Map<String, dynamic>))
      .toList();

  final signed = TxBuilder(net).buildSpend(
    utxos: utxos,
    toAddress: cfg['toAddress'] as String,
    amountSats: (cfg['amountSats'] as num).toInt(),
    changeAddress: acct0.bech32Address,
    wif: acct0.wif,
    feeRateSatPerVByte: (cfg['feeRateSatPerVByte'] as num).toDouble(),
  );

  stdout.writeln(jsonEncode({
    'rawHex': signed.rawHex,
    'txid': signed.txid,
    'feeSats': signed.feeSats,
    'changeSats': signed.changeSats,
    'inputs': signed.inputs.length,
  }));
}
