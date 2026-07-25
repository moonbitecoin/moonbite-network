import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

import 'package:moonbite_mobile/services/cert_pinning.dart';
import 'package:moonbite_mobile/services/chain_service.dart';

/// Guards the transport-security hardening: the explorer client must refuse
/// cleartext/downgraded URLs, and the production client must be certificate
/// pinned to the known root.
void main() {
  group('ChainService transport security', () {
    test('rejects a cleartext http base URL', () {
      expect(
        () => ChainService(
          baseUrl: 'http://insecure.example',
          httpClient: MockClient((_) async => http.Response('{}', 200)),
        ),
        throwsArgumentError,
      );
    });

    test('rejects a non-http scheme entirely', () {
      expect(
        () => ChainService(
          baseUrl: 'ftp://insecure.example',
          httpClient: MockClient((_) async => http.Response('{}', 200)),
        ),
        throwsArgumentError,
      );
    });

    test('accepts an https base URL', () {
      final svc = ChainService(
        baseUrl: 'https://ok.example',
        httpClient: MockClient((_) async => http.Response('{}', 200)),
      );
      expect(svc.baseUrl, 'https://ok.example');
    });

    test('setBaseUrl also refuses cleartext', () {
      final svc = ChainService(
        baseUrl: 'https://ok.example',
        httpClient: MockClient((_) async => http.Response('{}', 200)),
      );
      expect(() => svc.setBaseUrl('http://evil.example'), throwsArgumentError);
    });
  });

  group('certificate pinning', () {
    test('builds a pinned client without throwing', () {
      final client = createPinnedHttpClient();
      expect(client, isNotNull);
      client.close();
    });

    test('exposes the audited ISRG Root X2 SPKI pin', () {
      // A tripwire: if the embedded root is swapped, this must be updated
      // deliberately alongside it.
      expect(kIsrgRootX2SpkiPin,
          'diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=');
    });
  });
}
