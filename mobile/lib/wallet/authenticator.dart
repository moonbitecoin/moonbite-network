import 'package:local_auth/local_auth.dart';

/// Thrown when the user cannot prove presence (biometric / device credential)
/// before a fund-moving action. Callers must treat this as a hard stop: no
/// transaction is built, signed, or broadcast.
class AuthenticationException implements Exception {
  final String message;
  const AuthenticationException(this.message);
  @override
  String toString() => 'AuthenticationException: $message';
}

/// Gates sensitive, irreversible actions (spending) behind a local
/// presence check. Abstracted so tests can inject a deterministic stub
/// instead of touching the platform biometric channel.
abstract class Authenticator {
  /// Returns true only if the user actively confirmed their presence.
  Future<bool> authenticate(String reason);
}

/// Real implementation backed by the OS keyguard: biometrics when enrolled,
/// otherwise the device PIN/pattern/passcode (biometricOnly: false).
///
/// If the device has no secure lock configured at all, there is nothing to
/// gate against; we fail open so the wallet stays usable rather than bricking
/// every spend. On a device that *does* support auth, a cancelled or failed
/// prompt returns false and the caller aborts.
class LocalAuthenticator implements Authenticator {
  final LocalAuthentication _auth;
  LocalAuthenticator({LocalAuthentication? auth})
      : _auth = auth ?? LocalAuthentication();

  @override
  Future<bool> authenticate(String reason) async {
    final supported = await _auth.isDeviceSupported();
    if (!supported) return true;
    try {
      return await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          stickyAuth: true,
          biometricOnly: false,
        ),
      );
    } catch (_) {
      // Any platform error (no enrolment, locked out, channel failure) is
      // treated as "not authenticated" — fail closed for the spend.
      return false;
    }
  }
}
