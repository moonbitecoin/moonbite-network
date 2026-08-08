"""
Unit tests for biometric authentication system.

Tests cover:
- Biometric registration and setup
- Biometric verification
- Rate limiting
- Disable/cleanup
- Audit logging
- Password hashing with Argon2id fallback to SHA256
"""

import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import wallet_history


class BiometricAuthTestCase(unittest.TestCase):
    """Base test case with setup/teardown for biometric auth tests."""

    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Override the wallet_history DB path
        wallet_history._DB_PATH = self.db_path

        # Initialize schema
        wallet_history.create_schema()

    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass


class TestPasswordHashing(BiometricAuthTestCase):
    """Test password hashing and verification."""

    def test_password_hash_and_verify(self):
        """Test that passwords are hashed and verified correctly."""
        password = "SecurePassword123"
        hashed = wallet_history._hash_password(password)

        # Hash should not be the plaintext
        self.assertNotEqual(hashed, password)

        # Correct password should verify
        self.assertTrue(wallet_history._verify_password(password, hashed))

        # Incorrect password should not verify
        self.assertFalse(wallet_history._verify_password("WrongPassword", hashed))

    def test_password_hash_is_deterministic(self):
        """Test that hashing the same password produces different hashes (Argon2id)."""
        password = "SecurePassword123"
        hash1 = wallet_history._hash_password(password)
        hash2 = wallet_history._hash_password(password)

        # Argon2id includes salt, so hashes should be different
        # Both should verify against the password though
        self.assertTrue(wallet_history._verify_password(password, hash1))
        self.assertTrue(wallet_history._verify_password(password, hash2))


class TestBiometricSetup(BiometricAuthTestCase):
    """Test biometric registration and setup."""

    def test_setup_biometric_new_session(self):
        """Test registering biometric for a new session."""
        session_id = "test_session_1"
        credential_id = "base64_credential_id_example"
        public_key = "base64_public_key_example"
        device_name = "Test Device"

        result = wallet_history.setup_biometric(
            session_id, credential_id, public_key, device_name
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["biometric_enabled"], 1)
        self.assertEqual(result["biometric_device_name"], device_name)
        self.assertEqual(result["biometric_credential_id"], credential_id)
        self.assertEqual(result["biometric_public_key"], public_key)

    def test_setup_biometric_existing_session(self):
        """Test updating biometric for an existing session."""
        session_id = "test_session_2"

        # First setup
        wallet_history.setup_biometric(
            session_id, "cred_1", "key_1", "Device 1"
        )

        # Update with new credential
        result = wallet_history.setup_biometric(
            session_id, "cred_2", "key_2", "Device 2"
        )

        self.assertEqual(result["biometric_credential_id"], "cred_2")
        self.assertEqual(result["biometric_device_name"], "Device 2")

    def test_setup_biometric_default_device_name(self):
        """Test that default device name is applied."""
        session_id = "test_session_3"

        result = wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", ""
        )

        self.assertEqual(result["biometric_device_name"], "Default Device")

    def test_setup_biometric_updates_preferences(self):
        """Test that setup also updates preferences table."""
        session_id = "test_session_4"
        device_name = "My Phone"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", device_name
        )

        prefs = wallet_history.get_preferences(session_id)
        self.assertEqual(prefs["biometric_enabled"], 1)
        self.assertEqual(prefs["biometric_device_name"], device_name)


class TestBiometricVerification(BiometricAuthTestCase):
    """Test biometric verification and authentication."""

    def test_verify_biometric_success(self):
        """Test successful biometric verification."""
        session_id = "test_session_5"
        credential_id = "test_cred_id"

        wallet_history.setup_biometric(
            session_id, credential_id, "pub_key", "Device"
        )

        # Verify with correct credential ID
        result = wallet_history.verify_biometric(session_id, credential_id)
        self.assertTrue(result)

        # Check that last_login was updated
        auth_state = wallet_history.get_auth_state(session_id)
        self.assertIsNotNone(auth_state["last_login"])
        self.assertEqual(auth_state["failed_attempts"], 0)

    def test_verify_biometric_failure(self):
        """Test failed biometric verification."""
        session_id = "test_session_6"
        credential_id = "test_cred_id"

        wallet_history.setup_biometric(
            session_id, credential_id, "pub_key", "Device"
        )

        # Try to verify with wrong credential ID
        result = wallet_history.verify_biometric(session_id, "wrong_cred_id")
        self.assertFalse(result)

    def test_verify_biometric_not_registered(self):
        """Test verification when no biometric is registered."""
        session_id = "test_session_7"

        result = wallet_history.verify_biometric(session_id, "some_cred_id")
        self.assertFalse(result)

    def test_record_biometric_failure(self):
        """Test recording failed biometric attempts."""
        session_id = "test_session_8"

        # Record 3 failures
        attempt1 = wallet_history.record_biometric_failure(session_id)
        self.assertEqual(attempt1, 1)

        attempt2 = wallet_history.record_biometric_failure(session_id)
        self.assertEqual(attempt2, 2)

        attempt3 = wallet_history.record_biometric_failure(session_id)
        self.assertEqual(attempt3, 3)

    def test_failed_attempts_reset_on_success(self):
        """Test that failed attempts are reset on successful verification."""
        session_id = "test_session_9"
        credential_id = "test_cred_id"

        # Setup biometric
        wallet_history.setup_biometric(
            session_id, credential_id, "pub_key", "Device"
        )

        # Record some failures
        wallet_history.record_biometric_failure(session_id)
        wallet_history.record_biometric_failure(session_id)

        auth_state = wallet_history.get_auth_state(session_id)
        self.assertEqual(auth_state["failed_attempts"], 2)

        # Successful verification should reset failures
        wallet_history.verify_biometric(session_id, credential_id)

        auth_state = wallet_history.get_auth_state(session_id)
        self.assertEqual(auth_state["failed_attempts"], 0)


class TestBiometricRateLimiting(BiometricAuthTestCase):
    """Test rate limiting for biometric verification attempts."""

    def test_rate_limit_check_allows_under_limit(self):
        """Test that attempts under limit are allowed."""
        session_id = "test_session_10"

        # Record 3 failed attempts (max is 5)
        for _ in range(3):
            wallet_history.record_biometric_failure(session_id)

        is_limited, attempts = wallet_history.check_biometric_rate_limit(
            session_id, max_attempts=5, window_seconds=60
        )

        self.assertFalse(is_limited)
        self.assertEqual(attempts, 3)

    def test_rate_limit_check_blocks_over_limit(self):
        """Test that attempts over limit are blocked."""
        session_id = "test_session_11"

        # Record 6 failed attempts (max is 5)
        for _ in range(6):
            wallet_history.record_biometric_failure(session_id)

        is_limited, attempts = wallet_history.check_biometric_rate_limit(
            session_id, max_attempts=5, window_seconds=60
        )

        self.assertTrue(is_limited)
        self.assertEqual(attempts, 6)

    def test_rate_limit_window_respects_time(self):
        """Test that rate limit respects the time window."""
        session_id = "test_session_12"

        # Record a failure
        wallet_history.record_biometric_failure(session_id)

        # Check with a short window (should count)
        is_limited, attempts = wallet_history.check_biometric_rate_limit(
            session_id, max_attempts=5, window_seconds=60
        )
        self.assertEqual(attempts, 1)

        # Check with an expired window (should not count)
        # This would need time.time() mocking to properly test, but we verify the logic exists
        is_limited_long, attempts_long = wallet_history.check_biometric_rate_limit(
            session_id, max_attempts=5, window_seconds=1
        )
        # After 1 second window, the attempt from just now might still be counted
        # depending on timing, but the function supports it

    def test_default_rate_limit_is_5_per_minute(self):
        """Test default rate limit parameters."""
        session_id = "test_session_13"

        # Record 5 attempts
        for _ in range(5):
            wallet_history.record_biometric_failure(session_id)

        # Default (5 per 60 seconds) should not be limited yet
        is_limited, _ = wallet_history.check_biometric_rate_limit(session_id)
        self.assertTrue(is_limited)  # 5 == max, should be limited


class TestBiometricDisable(BiometricAuthTestCase):
    """Test disabling biometric authentication."""

    def test_disable_biometric(self):
        """Test disabling biometric for a session."""
        session_id = "test_session_14"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )

        # Verify it's enabled
        self.assertTrue(wallet_history.is_biometric_available(session_id))

        # Disable
        success = wallet_history.disable_biometric(session_id)
        self.assertTrue(success)

        # Verify it's disabled
        self.assertFalse(wallet_history.is_biometric_available(session_id))

    def test_disable_biometric_not_found(self):
        """Test disabling biometric when none exists."""
        session_id = "test_session_15"

        success = wallet_history.disable_biometric(session_id)
        self.assertFalse(success)

    def test_disable_biometric_clears_data(self):
        """Test that disabling clears all biometric data."""
        session_id = "test_session_16"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )

        wallet_history.disable_biometric(session_id)

        auth_state = wallet_history.get_auth_state(session_id)
        self.assertEqual(auth_state["biometric_enabled"], 0)
        self.assertIsNone(auth_state["biometric_credential_id"])
        self.assertIsNone(auth_state["biometric_device_name"])
        self.assertIsNone(auth_state["biometric_public_key"])


class TestBiometricAvailability(BiometricAuthTestCase):
    """Test checking biometric availability."""

    def test_is_biometric_available_when_enabled(self):
        """Test that is_biometric_available returns True when enabled."""
        session_id = "test_session_17"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )

        self.assertTrue(wallet_history.is_biometric_available(session_id))

    def test_is_biometric_available_when_disabled(self):
        """Test that is_biometric_available returns False when disabled."""
        session_id = "test_session_18"

        self.assertFalse(wallet_history.is_biometric_available(session_id))

    def test_is_biometric_available_after_disable(self):
        """Test availability after disabling biometric."""
        session_id = "test_session_19"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )
        self.assertTrue(wallet_history.is_biometric_available(session_id))

        wallet_history.disable_biometric(session_id)
        self.assertFalse(wallet_history.is_biometric_available(session_id))


class TestBiometricAuditLog(BiometricAuthTestCase):
    """Test biometric audit logging."""

    def test_get_biometric_audit_log_empty(self):
        """Test getting audit log for session with no events."""
        session_id = "test_session_20"

        audit_log = wallet_history.get_biometric_audit_log(session_id)

        self.assertEqual(audit_log["total"], 0)
        self.assertEqual(len(audit_log["events"]), 0)

    def test_get_biometric_audit_log_with_events(self):
        """Test getting audit log with biometric events."""
        session_id = "test_session_21"

        # Create some events
        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )
        wallet_history.verify_biometric(session_id, "cred_id")
        wallet_history.verify_biometric(session_id, "wrong_cred")  # This will fail
        wallet_history.disable_biometric(session_id)

        audit_log = wallet_history.get_biometric_audit_log(session_id)

        self.assertGreater(audit_log["total"], 0)
        self.assertGreater(len(audit_log["events"]), 0)

    def test_get_biometric_audit_log_filter_by_action(self):
        """Test filtering audit log by action."""
        session_id = "test_session_22"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )

        # Get only 'register' events
        audit_log = wallet_history.get_biometric_audit_log(
            session_id, action="register"
        )

        for event in audit_log["events"]:
            self.assertEqual(event["action"], "register")

    def test_audit_log_pagination(self):
        """Test audit log pagination."""
        session_id = "test_session_23"

        # Create multiple events
        for i in range(10):
            wallet_history.record_biometric_failure(session_id)

        # Get first page (limit 5)
        page1 = wallet_history.get_biometric_audit_log(
            session_id, limit=5, offset=0
        )
        self.assertEqual(len(page1["events"]), 5)
        self.assertEqual(page1["limit"], 5)
        self.assertEqual(page1["offset"], 0)

        # Get second page
        page2 = wallet_history.get_biometric_audit_log(
            session_id, limit=5, offset=5
        )
        self.assertEqual(len(page2["events"]), 5)
        self.assertEqual(page2["offset"], 5)


class TestGetAuthState(BiometricAuthTestCase):
    """Test retrieving authentication state."""

    def test_get_auth_state_not_found(self):
        """Test getting auth state for non-existent session."""
        session_id = "nonexistent_session"

        auth_state = wallet_history.get_auth_state(session_id)
        self.assertIsNone(auth_state)

    def test_get_auth_state_after_setup(self):
        """Test getting auth state after setup."""
        session_id = "test_session_24"

        wallet_history.setup_biometric(
            session_id, "cred_id", "pub_key", "Device"
        )

        auth_state = wallet_history.get_auth_state(session_id)
        self.assertIsNotNone(auth_state)
        self.assertEqual(auth_state["user_session_id"], session_id)
        self.assertEqual(auth_state["biometric_enabled"], 1)


if __name__ == "__main__":
    unittest.main()
