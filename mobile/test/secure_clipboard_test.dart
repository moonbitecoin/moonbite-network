import 'package:flutter_test/flutter_test.dart';
import 'package:moonbite_mobile/wallet/secure_clipboard.dart';

/// A recovery phrase copied to the clipboard must not linger there forever —
/// SecureClipboard wipes it after a delay, but only if the user has not since
/// copied something else. These tests drive it with an in-memory clipboard so
/// no Flutter engine or real delay is needed.
void main() {
  group('SecureClipboard.copyEphemeral', () {
    test('clears the secret after the delay when it is still on the clipboard',
        () async {
      final store = <String?>[null];
      final clip = SecureClipboard(
        clearAfter: const Duration(milliseconds: 5),
        write: (t) async => store[0] = t,
        read: () async => store[0],
      );

      final cleared = await clip.copyEphemeral('correct horse battery staple');

      expect(cleared, isTrue, reason: 'should report it wiped the clipboard');
      expect(store[0], '', reason: 'the phrase must be gone');
    });

    test('leaves a clipboard the user has since overwritten untouched',
        () async {
      final store = <String?>[null];
      final clip = SecureClipboard(
        clearAfter: const Duration(milliseconds: 20),
        write: (t) async => store[0] = t,
        read: () async => store[0],
      );

      final pending = clip.copyEphemeral('the twelve secret words');
      await Future<void>.delayed(Duration.zero); // let the write land
      expect(store[0], 'the twelve secret words');

      // The user copies something else before the timer fires.
      store[0] = 'unrelated user text';

      final cleared = await pending;
      expect(cleared, isFalse, reason: 'must not stomp new clipboard data');
      expect(store[0], 'unrelated user text');
    });
  });
}
