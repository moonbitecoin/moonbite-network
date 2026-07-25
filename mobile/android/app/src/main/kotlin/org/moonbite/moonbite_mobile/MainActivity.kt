package org.moonbite.moonbite_mobile

import io.flutter.embedding.android.FlutterFragmentActivity

// FlutterFragmentActivity (not FlutterActivity) is required by local_auth: the
// biometric prompt is a Fragment and needs a FragmentActivity host.
class MainActivity : FlutterFragmentActivity()
