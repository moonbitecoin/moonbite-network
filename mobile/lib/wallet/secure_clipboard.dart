import 'dart:async';

import 'package:flutter/services.dart';

/// Copies short-lived secrets (like a recovery phrase) to the clipboard and
/// automatically wipes them after a delay.
///
/// A recovery phrase left on the clipboard is readable by every other app and
/// survives until overwritten. We clear it after [clearAfter], but only if the
/// clipboard STILL holds our secret — if the user copied something else in the
/// meantime we must not stomp on their new clipboard contents.
///
/// The [SystemClipboard] read/write functions are injected so the auto-clear
/// logic can be unit-tested without a running Flutter engine.
class SecureClipboard {
  SecureClipboard({
    Duration? clearAfter,
    Future<void> Function(String text)? write,
    Future<String?> Function()? read,
  })  : clearAfter = clearAfter ?? const Duration(seconds: 30),
        _write = write ?? _defaultWrite,
        _read = read ?? _defaultRead;

  final Duration clearAfter;
  final Future<void> Function(String text) _write;
  final Future<String?> Function() _read;

  static Future<void> _defaultWrite(String text) =>
      Clipboard.setData(ClipboardData(text: text));

  static Future<String?> _defaultRead() async =>
      (await Clipboard.getData(Clipboard.kTextPlain))?.text;

  /// Copies [secret], then schedules a wipe. Returns the pending clear so
  /// callers (and tests) can await it. The returned future resolves to `true`
  /// if the clipboard was actually cleared, or `false` if it had already
  /// changed and was left untouched.
  Future<bool> copyEphemeral(String secret) async {
    await _write(secret);
    return Future<bool>.delayed(clearAfter, () async {
      final current = await _read();
      if (current == secret) {
        await _write('');
        return true;
      }
      return false;
    });
  }
}
