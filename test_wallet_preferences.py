"""Test suite for wallet preferences functionality."""

import unittest
import tempfile
import os
from wallet_history import (
    get_connection,
    get_preference_defaults,
    validate_preference_value,
    get_preferences,
    update_preferences,
    reset_preferences,
    delete_preferences,
    create_schema,
)


class TestPreferences(unittest.TestCase):
    """Test wallet preferences schema and functions."""

    @classmethod
    def setUpClass(cls):
        """Set up a temporary database for testing."""
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        os.environ['MOONBITE_WALLET_HISTORY_DB'] = cls.db_path

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary database."""
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def setUp(self):
        """Create schema before each test."""
        create_schema()

    def test_preference_defaults(self):
        """Test that defaults are properly defined."""
        defaults = get_preference_defaults()

        self.assertEqual(defaults['language'], 'en')
        self.assertEqual(defaults['currency'], 'USD')
        self.assertEqual(defaults['theme'], 'auto')
        self.assertEqual(defaults['time_format'], 'relative')
        self.assertEqual(defaults['amount_format'], 'full')
        self.assertEqual(defaults['notification_tx'], 1)
        self.assertEqual(defaults['notification_price'], 1)
        self.assertEqual(defaults['auto_lock_mins'], 15)
        self.assertEqual(defaults['decimal_places'], 8)
        self.assertEqual(defaults['hide_zero_balance'], 0)
        self.assertEqual(defaults['sort_accounts'], 'created')

    def test_validate_language(self):
        """Test language preference validation."""
        # Valid languages
        for lang in ['en', 'es', 'fr', 'de', 'ja', 'zh']:
            self.assertTrue(validate_preference_value('language', lang))

        # Invalid language
        with self.assertRaises(ValueError):
            validate_preference_value('language', 'invalid')

    def test_validate_theme(self):
        """Test theme preference validation."""
        for theme in ['light', 'dark', 'auto']:
            self.assertTrue(validate_preference_value('theme', theme))

        with self.assertRaises(ValueError):
            validate_preference_value('theme', 'neon')

    def test_validate_currency(self):
        """Test currency preference validation."""
        currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'BTC', 'MBITE']
        for curr in currencies:
            self.assertTrue(validate_preference_value('currency', curr))

        with self.assertRaises(ValueError):
            validate_preference_value('currency', 'XXX')

    def test_validate_decimal_places(self):
        """Test decimal_places range validation."""
        # Valid values
        self.assertTrue(validate_preference_value('decimal_places', 2))
        self.assertTrue(validate_preference_value('decimal_places', 8))

        # Invalid values (out of range)
        with self.assertRaises(ValueError):
            validate_preference_value('decimal_places', 1)

        with self.assertRaises(ValueError):
            validate_preference_value('decimal_places', 9)

    def test_validate_auto_lock_mins(self):
        """Test auto_lock_mins range validation."""
        # Valid values
        self.assertTrue(validate_preference_value('auto_lock_mins', 0))
        self.assertTrue(validate_preference_value('auto_lock_mins', 15))
        self.assertTrue(validate_preference_value('auto_lock_mins', 120))

        # Invalid values
        with self.assertRaises(ValueError):
            validate_preference_value('auto_lock_mins', -1)

        with self.assertRaises(ValueError):
            validate_preference_value('auto_lock_mins', 121)

    def test_validate_notification_flags(self):
        """Test notification flags validation."""
        self.assertTrue(validate_preference_value('notification_tx', 0))
        self.assertTrue(validate_preference_value('notification_tx', 1))
        self.assertTrue(validate_preference_value('notification_price', 0))
        self.assertTrue(validate_preference_value('notification_price', 1))

        with self.assertRaises(ValueError):
            validate_preference_value('notification_tx', 2)

    def test_validate_type_checking(self):
        """Test that type validation is enforced."""
        # String field with int value
        with self.assertRaises(ValueError):
            validate_preference_value('language', 123)

        # Int field with string value
        with self.assertRaises(ValueError):
            validate_preference_value('auto_lock_mins', 'fifteen')

    def test_validate_unknown_key(self):
        """Test that unknown keys are rejected."""
        with self.assertRaises(ValueError):
            validate_preference_value('nonexistent', 'value')

    def test_get_preferences_new_user(self):
        """Test getting preferences for new user returns defaults."""
        session_id = 'test-session-1'
        prefs = get_preferences(session_id)

        # Should have all default keys
        self.assertEqual(prefs['language'], 'en')
        self.assertEqual(prefs['currency'], 'USD')
        self.assertEqual(prefs['theme'], 'auto')

    def test_update_preferences_creates_entry(self):
        """Test that update_preferences creates entry if doesn't exist."""
        session_id = 'test-session-2'

        # Update non-existent preferences
        result = update_preferences(session_id, {'theme': 'dark'})

        self.assertEqual(result['theme'], 'dark')
        self.assertEqual(result['language'], 'en')  # Default

        # Verify in database
        prefs = get_preferences(session_id)
        self.assertEqual(prefs['theme'], 'dark')

    def test_update_multiple_preferences(self):
        """Test updating multiple preferences at once."""
        session_id = 'test-session-3'

        updates = {
            'theme': 'light',
            'currency': 'EUR',
            'auto_lock_mins': 30,
            'decimal_places': 4,
        }

        result = update_preferences(session_id, updates)

        for key, value in updates.items():
            self.assertEqual(result[key], value)

    def test_update_single_preference(self):
        """Test updating a single preference preserves others."""
        session_id = 'test-session-4'

        # Set initial preferences
        update_preferences(session_id, {'theme': 'dark', 'currency': 'EUR'})

        # Update only one
        result = update_preferences(session_id, {'theme': 'light'})

        self.assertEqual(result['theme'], 'light')
        self.assertEqual(result['currency'], 'EUR')  # Preserved

    def test_reset_preferences(self):
        """Test resetting preferences to defaults."""
        session_id = 'test-session-5'

        # Set custom preferences
        update_preferences(session_id, {
            'theme': 'light',
            'currency': 'GBP',
            'auto_lock_mins': 60,
        })

        # Reset
        result = reset_preferences(session_id)

        self.assertEqual(result['theme'], 'auto')  # Default
        self.assertEqual(result['currency'], 'USD')  # Default
        self.assertEqual(result['auto_lock_mins'], 15)  # Default

    def test_delete_preferences(self):
        """Test deleting preferences."""
        session_id = 'test-session-6'

        # Create preferences
        update_preferences(session_id, {'theme': 'dark'})

        # Verify exists
        prefs = get_preferences(session_id)
        self.assertEqual(prefs['theme'], 'dark')

        # Delete
        success = delete_preferences(session_id)
        self.assertTrue(success)

        # After delete, should get defaults
        prefs = get_preferences(session_id)
        self.assertEqual(prefs['theme'], 'auto')  # Default, not stored

    def test_delete_nonexistent_preferences(self):
        """Test deleting non-existent preferences."""
        session_id = 'test-session-nonexistent'
        success = delete_preferences(session_id)
        self.assertFalse(success)

    def test_session_isolation(self):
        """Test that preferences are isolated by session."""
        session1 = 'session-1'
        session2 = 'session-2'

        # Set different preferences for each session
        update_preferences(session1, {'theme': 'dark', 'currency': 'EUR'})
        update_preferences(session2, {'theme': 'light', 'currency': 'GBP'})

        # Verify isolation
        prefs1 = get_preferences(session1)
        prefs2 = get_preferences(session2)

        self.assertEqual(prefs1['theme'], 'dark')
        self.assertEqual(prefs1['currency'], 'EUR')

        self.assertEqual(prefs2['theme'], 'light')
        self.assertEqual(prefs2['currency'], 'GBP')

    def test_validation_before_update(self):
        """Test that invalid values are rejected before update."""
        session_id = 'test-session-7'

        # Try to update with invalid value
        with self.assertRaises(ValueError):
            update_preferences(session_id, {'theme': 'invalid'})

        # Should not have created entry with invalid data
        # (validation happens before database write)

    def test_time_format_options(self):
        """Test time_format preference options."""
        formats = ['relative', 'absolute', 'unix']
        for fmt in formats:
            self.assertTrue(validate_preference_value('time_format', fmt))

        with self.assertRaises(ValueError):
            validate_preference_value('time_format', 'iso')

    def test_amount_format_options(self):
        """Test amount_format preference options."""
        formats = ['full', 'short', 'scientific']
        for fmt in formats:
            self.assertTrue(validate_preference_value('amount_format', fmt))

    def test_sort_accounts_options(self):
        """Test sort_accounts preference options."""
        sorts = ['created', 'updated', 'name', 'balance']
        for sort in sorts:
            self.assertTrue(validate_preference_value('sort_accounts', sort))


class TestPreferencesIntegration(unittest.TestCase):
    """Integration tests for preferences with Flask."""

    @classmethod
    def setUpClass(cls):
        """Set up a temporary database for testing."""
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        os.environ['MOONBITE_WALLET_HISTORY_DB'] = cls.db_path
        create_schema()

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary database."""
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def test_workflow_create_update_reset(self):
        """Test complete workflow: create, update, reset."""
        session_id = 'workflow-test'

        # 1. Get defaults (new user)
        prefs = get_preferences(session_id)
        self.assertEqual(prefs['theme'], 'auto')

        # 2. Update preferences
        result = update_preferences(session_id, {
            'theme': 'dark',
            'currency': 'EUR',
            'notification_tx': 0,
        })
        self.assertEqual(result['theme'], 'dark')
        self.assertEqual(result['currency'], 'EUR')
        self.assertEqual(result['notification_tx'], 0)

        # 3. Verify persistence
        prefs = get_preferences(session_id)
        self.assertEqual(prefs['theme'], 'dark')

        # 4. Reset
        result = reset_preferences(session_id)
        self.assertEqual(result['theme'], 'auto')
        self.assertEqual(result['currency'], 'USD')


if __name__ == '__main__':
    unittest.main()
