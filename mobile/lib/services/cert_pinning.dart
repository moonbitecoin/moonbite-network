import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

/// TLS certificate pinning for the explorer connection.
///
/// The wallet's keys never leave the device, but a man-in-the-middle on the
/// explorer link could still feed the wallet false chain state (fake balances /
/// UTXOs) or observe the user's addresses. Ordinary HTTPS trusts every CA in
/// the OS store, so a single rogue or coerced CA — or a locally-installed
/// interception root — is enough to MITM.
///
/// We pin to Let's Encrypt's ISRG Root X2, the root the live endpoint
/// (moonbite-production.up.railway.app) chains to. Pinning the *root* (not the
/// short-lived leaf) survives normal 90-day leaf/intermediate renewals while
/// still rejecting any certificate issued by a different CA.
///
/// SPKI SHA-256 pin (base64) of the key below, for auditing:
///   diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=
/// Verified against the live TLS handshake. Valid until 2032-09-02.
///
/// OPERATIONAL NOTE: if the endpoint's CA chain ever changes (e.g. the host
/// migrates off Let's Encrypt), this root must be updated and the app
/// re-released, otherwise every request will fail closed. That availability
/// cost is the deliberate price of pinning.
const String kIsrgRootX2SpkiPin =
    'diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=';

const String _isrgRootX2Pem = '''
-----BEGIN CERTIFICATE-----
MIIEcDCCAligAwIBAgIQbI8dxyfHEX97r4U6yYD5zTANBgkqhkiG9w0BAQsFADBP
MQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFy
Y2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBYMTAeFw0yNjA1MTMwMDAwMDBa
Fw0zMjA5MDIyMzU5NTlaME8xCzAJBgNVBAYTAlVTMSkwJwYDVQQKEyBJbnRlcm5l
dCBTZWN1cml0eSBSZXNlYXJjaCBHcm91cDEVMBMGA1UEAxMMSVNSRyBSb290IFgy
MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEzZvVn4CDCuwJSvMWSj5cz3es3mcFDR0H
ttwW+1qLFNvicWDEukWVEYmO6gbf9yoWHKS5xcUy4APgHoIYOIvXRdgKam7mAHf7
AlF9ItgKbppbd9/w+kHsOdx1ymgHDB/qo4H1MIHyMA4GA1UdDwEB/wQEAwIBBjAd
BgNVHSUEFjAUBggrBgEFBQcDAQYIKwYBBQUHAwIwDwYDVR0TAQH/BAUwAwEB/zAd
BgNVHQ4EFgQUfEKWrt5LSDv6kviejM9ti6lyN5UwHwYDVR0jBBgwFoAUebRZ5nu2
5eQBc4AIiMgaWPbpm24wMgYIKwYBBQUHAQEEJjAkMCIGCCsGAQUFBzAChhZodHRw
Oi8veDEuaS5sZW5jci5vcmcvMBMGA1UdIAQMMAowCAYGZ4EMAQIBMCcGA1UdHwQg
MB4wHKAaoBiGFmh0dHA6Ly94MS5jLmxlbmNyLm9yZy8wDQYJKoZIhvcNAQELBQAD
ggIBAD2/e9frmMxNpCV03qUHegg+MV2wz9644YoXdqtH8RyWYcBO7xfjjGEXdU1e
/o0OkEFiynUCOSIk/vLLo7ttz6CPAeNlWfC0XNkoGeWgK6jjXvozBaGuGH5n0Ufo
shMeWTuURqNN5G00sSXDTBrpp2+mgvdZQjb8K11TYMA25QA+YHNfbIEL0BniAhKS
2gsnJjSzrdZLI+EZ7SEyqdR2rkjd1KutLDU+n3TFyxjniZVGur4YlhMP3mY/dV95
IruAkkjOZier6hGBdEgZXXvaCz9u9iVEadsIE75pAGL8oHV5vxdARDiotRpul1IN
/UZwzAbrfUFcw1HkAcYD/mlZfnQ2ieCF2MS7j3Vhv7JPDKp45fmykmzYNSrumRW0
upFFKDBOoF7hsOb7oLyHS+Uft6jOUfOrogj8YUx38hKb2K20r42OgsSdDdxdeYWc
MS3Sb6mwJeSZEYxJ2gaXnDSPaKhhrNkYwljyVQyr4Nq+MEJytXNTnHqaAcrNwZlV
pcJL1KBnMrMjP7eanvUwL3FYj3cF17jtboLt7gLoi4+2rWZFvn+w54jmd/FIuhhZ
cEaU/wvU6BUNMtcVquVGHp7itQeDth5j+XL3j4WJ2SABwzUl6OeYdgpIt/ITZa+p
TT0mQ/r5XyA4MEAiabn7XJjvCERlF2dcn2wqJw+CreTkkQ2R
-----END CERTIFICATE-----
''';

/// Builds an [http.Client] that only trusts certificates chaining to the pinned
/// ISRG root. [withTrustedRoots] is false, so the OS trust store is ignored and
/// a MITM certificate from any other CA fails the handshake. A cert that fails
/// validation is rejected outright (badCertificateCallback returns false).
http.Client createPinnedHttpClient() {
  final context = SecurityContext(withTrustedRoots: false)
    ..setTrustedCertificatesBytes(utf8.encode(_isrgRootX2Pem));
  final inner = HttpClient(context: context)
    ..badCertificateCallback = (cert, host, port) => false;
  return IOClient(inner);
}
