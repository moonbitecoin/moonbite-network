import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Repo guards for the Android release ship-blockers. These read the build
/// config / manifest / resource files and assert the hardened attributes are
/// present, so a regression (e.g. someone re-adds the debug signing key) fails
/// CI instead of silently shipping. Paths are relative to the package root,
/// which is where `flutter test` runs.
File _f(String relative) {
  final f = File(relative);
  expect(f.existsSync(), isTrue, reason: 'expected file: $relative');
  return f;
}

void main() {
  group('release signing (build.gradle.kts)', () {
    late String gradle;
    setUpAll(() => gradle = _f('android/app/build.gradle.kts').readAsStringSync());

    test('does not sign the release build with the debug key', () {
      expect(
        gradle.contains('signingConfigs.getByName("debug")'),
        isFalse,
        reason: 'release must not fall back to the debug keystore',
      );
    });

    test('wires a real release signing config from key.properties', () {
      expect(gradle.contains('key.properties'), isTrue);
      expect(gradle.contains('signingConfigs.getByName("release")'), isTrue);
    });

    test('fails the build when the keystore is absent', () {
      expect(gradle.contains('GradleException'), isTrue,
          reason: 'a missing key.properties must hard-fail, not warn');
    });

    test('uses the MoonBite application id, not the old bigcoin one', () {
      expect(gradle.contains('org.moonbite.moonbite_mobile'), isTrue);
      expect(gradle.contains('org.bigcoin.bigcoin_mobile'), isFalse);
    });
  });

  group('AndroidManifest hardening', () {
    late String manifest;
    setUpAll(() => manifest =
        _f('android/app/src/main/AndroidManifest.xml').readAsStringSync());

    test('disables OS backup of the app sandbox', () {
      expect(manifest.contains('android:allowBackup="false"'), isTrue);
    });

    test('points at the network security config', () {
      expect(
        manifest.contains(
            'android:networkSecurityConfig="@xml/network_security_config"'),
        isTrue,
      );
    });

    test('declares the INTERNET permission for the release build', () {
      expect(
        manifest.contains('android.permission.INTERNET'),
        isTrue,
      );
    });

    test('declares the biometric permission for the spend gate', () {
      expect(
        manifest.contains('android.permission.USE_BIOMETRIC'),
        isTrue,
      );
    });
  });

  group('biometric host activity', () {
    late String kt;
    setUpAll(() => kt = _f(
            'android/app/src/main/kotlin/org/moonbite/moonbite_mobile/MainActivity.kt')
        .readAsStringSync());

    test('MainActivity extends FlutterFragmentActivity for local_auth', () {
      // local_auth's prompt is a Fragment; a plain FlutterActivity can't host
      // it and the biometric gate would crash at runtime.
      expect(kt.contains('FlutterFragmentActivity'), isTrue);
      expect(
        kt.contains(': FlutterActivity()'),
        isFalse,
        reason: 'must not extend the non-fragment FlutterActivity',
      );
    });

    test('sets FLAG_SECURE to block screenshots of seed/balances', () {
      expect(
        kt.contains('FLAG_SECURE'),
        isTrue,
        reason: 'the recovery phrase and balances must not leak into screen '
            'captures or the recent-apps thumbnail',
      );
    });
  });

  group('network security config', () {
    test('forbids cleartext (plain HTTP) traffic', () {
      final xml = _f('android/app/src/main/res/xml/network_security_config.xml')
          .readAsStringSync();
      expect(xml.contains('cleartextTrafficPermitted="false"'), isTrue);
    });
  });

  group('stale bigcoin package', () {
    test('the old MainActivity.kt is gone', () {
      expect(
        File('android/app/src/main/kotlin/org/bigcoin/bigcoin_mobile/MainActivity.kt')
            .existsSync(),
        isFalse,
      );
    });

    test('the MoonBite MainActivity.kt exists', () {
      _f('android/app/src/main/kotlin/org/moonbite/moonbite_mobile/MainActivity.kt');
    });
  });
}
