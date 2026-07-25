import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../wallet/wallet_controller.dart';

/// Gate shown when a wallet exists on the device but has not been unlocked this
/// session. Auto-prompts for biometrics/PIN once on display; if the owner
/// cancels or fails, a retry button remains so they are never stuck.
class LockScreen extends StatefulWidget {
  const LockScreen({super.key});

  @override
  State<LockScreen> createState() => _LockScreenState();
}

class _LockScreenState extends State<LockScreen> {
  bool _attempting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _attemptUnlock());
  }

  Future<void> _attemptUnlock() async {
    if (_attempting) return;
    setState(() => _attempting = true);
    try {
      await context.read<WalletController>().unlock();
    } finally {
      if (mounted) setState(() => _attempting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lock_outline,
                  size: 72, color: Color(0xFF1F6FD9)),
              const SizedBox(height: 16),
              const Text(
                'MoonBite Wallet is locked',
                style: TextStyle(fontSize: 18, color: Colors.white),
              ),
              const SizedBox(height: 8),
              const Text(
                'Authenticate to view your balance and address.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white70, fontSize: 13),
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                icon: const Icon(Icons.fingerprint),
                label: Text(_attempting ? 'Unlocking…' : 'Unlock'),
                onPressed: _attempting ? null : _attemptUnlock,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
