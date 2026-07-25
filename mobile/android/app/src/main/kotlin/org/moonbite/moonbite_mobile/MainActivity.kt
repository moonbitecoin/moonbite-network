package org.moonbite.moonbite_mobile

import android.os.Bundle
import android.view.WindowManager
import io.flutter.embedding.android.FlutterFragmentActivity

// FlutterFragmentActivity (not FlutterActivity) is required by local_auth: the
// biometric prompt is a Fragment and needs a FragmentActivity host.
class MainActivity : FlutterFragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // FLAG_SECURE blocks screenshots, screen recording, and excludes the
        // window from the recent-apps thumbnail. The wallet shows the recovery
        // phrase and balances; those must not leak into screen captures or the
        // task switcher preview.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE,
        )
        super.onCreate(savedInstanceState)
    }
}
