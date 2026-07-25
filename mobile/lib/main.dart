import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'services/chain_service.dart';
import 'screens/home_screen.dart';
import 'screens/lock_screen.dart';
import 'screens/onboarding_screen.dart';
import 'wallet/wallet_controller.dart';

void main() {
  runApp(const MoonBiteApp());
}

class MoonBiteApp extends StatelessWidget {
  const MoonBiteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ChainService>(create: (_) => ChainService()),
        ChangeNotifierProvider<WalletController>(
          create: (ctx) =>
              WalletController(chain: ctx.read<ChainService>()),
        ),
      ],
      child: MaterialApp(
        title: 'MoonBite Wallet',
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark(useMaterial3: true).copyWith(
          scaffoldBackgroundColor: const Color(0xFF121212),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF1F6FD9),
            secondary: Color(0xFF1F6FD9),
          ),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF1F1F1F),
            elevation: 0,
          ),
          bottomNavigationBarTheme: const BottomNavigationBarThemeData(
            backgroundColor: Color(0xFF1F1F1F),
            selectedItemColor: Color(0xFF1F6FD9),
            unselectedItemColor: Color(0xFF666666),
          ),
        ),
        home: const _Root(),
      ),
    );
  }
}

/// Decides between onboarding and the main app depending on whether a wallet
/// already exists on the device.
class _Root extends StatefulWidget {
  const _Root();

  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> with WidgetsBindingObserver {
  late final Future<bool> _loaded;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loaded = context.read<WalletController>().loadExisting();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Re-engage the lock whenever the app leaves the foreground so a stored
    // wallet always requires a fresh unlock on return.
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      context.read<WalletController>().lock();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _loaded,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        final controller = context.watch<WalletController>();
        if (!controller.hasWallet) {
          return const OnboardingScreen();
        }
        return controller.requiresUnlock
            ? const LockScreen()
            : const HomeScreen();
      },
    );
  }
}
