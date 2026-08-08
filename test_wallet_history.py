#!/usr/bin/env python
"""Unit tests for wallet_history module — transaction history and address book."""

import os
import sys
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

# Use temp database for testing
_test_db = "test_wallet_history.db"
os.environ["MOONBITE_WALLET_HISTORY_DB"] = _test_db

import wallet_history


class TestTransactionHistory(unittest.TestCase):
    """Test transaction tracking functionality."""

    def setUp(self):
        """Create a fresh database for each test."""
        # Clean up database tables for each test
        self.session_id = "test_session_123"
        try:
            conn = wallet_history.get_connection()
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM address_book")
            conn.commit()
            conn.close()
        except Exception:
            pass
        wallet_history.create_schema()

    def tearDown(self):
        """Clean up."""
        pass

    def test_add_transaction_send(self):
        """Test adding a send transaction."""
        tx = wallet_history.add_transaction(
            session_id=self.session_id,
            txid="abcd1234",
            direction="send",
            amount_units=50000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
            fee_units=100,
            status="pending",
            memo="Payment for lunch",
        )
        self.assertEqual(tx["txid"], "abcd1234")
        self.assertEqual(tx["direction"], "send")
        self.assertEqual(tx["amount_units"], 50000)
        self.assertEqual(tx["fee_units"], 100)
        self.assertEqual(tx["status"], "pending")
        self.assertEqual(tx["memo"], "Payment for lunch")

    def test_add_transaction_receive(self):
        """Test adding a receive transaction."""
        tx = wallet_history.add_transaction(
            session_id=self.session_id,
            txid="efgh5678",
            direction="receive",
            amount_units=100000,
            from_address="moon3zzzzz",
            to_address="moon1xxxxx",
            status="confirmed",
            block_height=100,
            confirmations=5,
        )
        self.assertEqual(tx["direction"], "receive")
        self.assertEqual(tx["amount_units"], 100000)
        self.assertEqual(tx["status"], "confirmed")
        self.assertEqual(tx["block_height"], 100)
        self.assertEqual(tx["confirmations"], 5)

    def test_get_transaction(self):
        """Test retrieving a single transaction."""
        wallet_history.add_transaction(
            session_id=self.session_id,
            txid="abcd1234",
            direction="send",
            amount_units=50000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
        )
        tx = wallet_history.get_transaction(self.session_id, "abcd1234")
        self.assertIsNotNone(tx)
        self.assertEqual(tx["txid"], "abcd1234")

    def test_get_transaction_not_found(self):
        """Test retrieving a non-existent transaction."""
        tx = wallet_history.get_transaction(self.session_id, "nonexistent")
        self.assertIsNone(tx)

    def test_get_transactions_list(self):
        """Test listing transactions with pagination."""
        # Add multiple transactions
        for i in range(5):
            wallet_history.add_transaction(
                session_id=self.session_id,
                txid=f"tx_{i}",
                direction="send" if i % 2 == 0 else "receive",
                amount_units=1000 * (i + 1),
                from_address="moon1xxxxx",
                to_address="moon2yyyyy",
            )

        # Get first page
        result = wallet_history.get_transactions(self.session_id, limit=3, offset=0)
        self.assertEqual(len(result["transactions"]), 3)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["limit"], 3)
        self.assertEqual(result["offset"], 0)

        # Get second page
        result = wallet_history.get_transactions(self.session_id, limit=3, offset=3)
        self.assertEqual(len(result["transactions"]), 2)

    def test_filter_transactions_by_status(self):
        """Test filtering transactions by status."""
        wallet_history.add_transaction(
            session_id=self.session_id,
            txid="tx_pending",
            direction="send",
            amount_units=1000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
            status="pending",
        )
        wallet_history.add_transaction(
            session_id=self.session_id,
            txid="tx_confirmed",
            direction="send",
            amount_units=2000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
            status="confirmed",
        )

        pending = wallet_history.get_transactions(self.session_id, status="pending")
        self.assertEqual(len(pending["transactions"]), 1)
        self.assertEqual(pending["transactions"][0]["status"], "pending")

        confirmed = wallet_history.get_transactions(self.session_id, status="confirmed")
        self.assertEqual(len(confirmed["transactions"]), 1)
        self.assertEqual(confirmed["transactions"][0]["status"], "confirmed")

    def test_update_transaction_memo(self):
        """Test updating a transaction memo."""
        wallet_history.add_transaction(
            session_id=self.session_id,
            txid="abcd1234",
            direction="send",
            amount_units=50000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
            memo="Original memo",
        )

        updated = wallet_history.update_transaction_memo(
            self.session_id, "abcd1234", "Updated memo"
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["memo"], "Updated memo")

        # Verify persistence
        fetched = wallet_history.get_transaction(self.session_id, "abcd1234")
        self.assertEqual(fetched["memo"], "Updated memo")

    def test_session_isolation(self):
        """Test that transactions are isolated by session ID."""
        session_2 = "test_session_456"

        # Add transaction to session 1
        wallet_history.add_transaction(
            session_id=self.session_id,
            txid="tx_session1",
            direction="send",
            amount_units=1000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
        )

        # Add transaction to session 2
        wallet_history.add_transaction(
            session_id=session_2,
            txid="tx_session2",
            direction="send",
            amount_units=2000,
            from_address="moon1xxxxx",
            to_address="moon2yyyyy",
        )

        # Verify isolation
        result1 = wallet_history.get_transactions(self.session_id)
        self.assertEqual(len(result1["transactions"]), 1)
        self.assertEqual(result1["transactions"][0]["txid"], "tx_session1")

        result2 = wallet_history.get_transactions(session_2)
        self.assertEqual(len(result2["transactions"]), 1)
        self.assertEqual(result2["transactions"][0]["txid"], "tx_session2")


class TestAddressBook(unittest.TestCase):
    """Test address book functionality."""

    def setUp(self):
        """Create a fresh database for each test."""
        # Clean up database tables for each test
        self.session_id = "test_session_abc"
        try:
            conn = wallet_history.get_connection()
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM address_book")
            conn.commit()
            conn.close()
        except Exception:
            pass
        wallet_history.create_schema()

    def test_add_contact(self):
        """Test adding a contact."""
        contact = wallet_history.add_contact(
            session_id=self.session_id,
            label="Alice",
            address="moon1alice",
            category="friends",
            notes="College friend",
        )
        self.assertEqual(contact["label"], "Alice")
        self.assertEqual(contact["address"], "moon1alice")
        self.assertEqual(contact["category"], "friends")
        self.assertEqual(contact["notes"], "College friend")
        self.assertEqual(contact["times_sent"], 0)

    def test_add_contact_duplicate_label(self):
        """Test that duplicate labels are rejected."""
        wallet_history.add_contact(
            session_id=self.session_id,
            label="Bob",
            address="moon1bob",
        )
        with self.assertRaises(ValueError):
            wallet_history.add_contact(
                session_id=self.session_id,
                label="Bob",
                address="moon1bob2",
            )

    def test_get_contact(self):
        """Test retrieving a single contact."""
        added = wallet_history.add_contact(
            session_id=self.session_id,
            label="Charlie",
            address="moon1charlie",
        )
        retrieved = wallet_history.get_contact(self.session_id, added["id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["label"], "Charlie")

    def test_get_contacts_list(self):
        """Test listing all contacts."""
        for i in range(3):
            wallet_history.add_contact(
                session_id=self.session_id,
                label=f"Contact{i}",
                address=f"moon{i}",
                category="general" if i % 2 == 0 else "work",
            )

        contacts = wallet_history.get_contacts(self.session_id)
        self.assertEqual(len(contacts), 3)

    def test_filter_contacts_by_category(self):
        """Test filtering contacts by category."""
        wallet_history.add_contact(
            session_id=self.session_id,
            label="Work1",
            address="moon1work1",
            category="work",
        )
        wallet_history.add_contact(
            session_id=self.session_id,
            label="Friend1",
            address="moon1friend1",
            category="friends",
        )

        work = wallet_history.get_contacts(self.session_id, category="work")
        self.assertEqual(len(work), 1)
        self.assertEqual(work[0]["label"], "Work1")

        friends = wallet_history.get_contacts(self.session_id, category="friends")
        self.assertEqual(len(friends), 1)
        self.assertEqual(friends[0]["label"], "Friend1")

    def test_sort_contacts(self):
        """Test sorting contacts by different fields."""
        for label in ["Z", "A", "M"]:
            wallet_history.add_contact(
                session_id=self.session_id,
                label=label,
                address=f"moon_{label}",
            )

        # Sort by label
        sorted_by_label = wallet_history.get_contacts(self.session_id, sort="label")
        labels = [c["label"] for c in sorted_by_label]
        self.assertEqual(labels, ["A", "M", "Z"])

    def test_update_contact(self):
        """Test updating a contact."""
        added = wallet_history.add_contact(
            session_id=self.session_id,
            label="Dave",
            address="moon1dave",
            category="general",
        )

        updated = wallet_history.update_contact(
            self.session_id,
            added["id"],
            {"label": "David", "category": "work", "is_favorite": 1},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["label"], "David")
        self.assertEqual(updated["category"], "work")
        self.assertEqual(updated["is_favorite"], 1)

    def test_increment_send_count(self):
        """Test incrementing the send counter."""
        added = wallet_history.add_contact(
            session_id=self.session_id,
            label="Eve",
            address="moon1eve",
        )

        # Increment twice
        wallet_history.increment_send_count(self.session_id, added["id"])
        wallet_history.increment_send_count(self.session_id, added["id"])

        retrieved = wallet_history.get_contact(self.session_id, added["id"])
        self.assertEqual(retrieved["times_sent"], 2)
        self.assertIsNotNone(retrieved["last_sent"])

    def test_delete_contact(self):
        """Test deleting a contact."""
        added = wallet_history.add_contact(
            session_id=self.session_id,
            label="Frank",
            address="moon1frank",
        )

        deleted = wallet_history.delete_contact(self.session_id, added["id"])
        self.assertTrue(deleted)

        retrieved = wallet_history.get_contact(self.session_id, added["id"])
        self.assertIsNone(retrieved)

    def test_session_isolation_contacts(self):
        """Test that contacts are isolated by session ID."""
        session_2 = "test_session_xyz"

        wallet_history.add_contact(
            session_id=self.session_id,
            label="Grace",
            address="moon1grace",
        )
        wallet_history.add_contact(
            session_id=session_2,
            label="Henry",
            address="moon1henry",
        )

        contacts1 = wallet_history.get_contacts(self.session_id)
        contacts2 = wallet_history.get_contacts(session_2)

        self.assertEqual(len(contacts1), 1)
        self.assertEqual(contacts1[0]["label"], "Grace")

        self.assertEqual(len(contacts2), 1)
        self.assertEqual(contacts2[0]["label"], "Henry")

    def test_export_import_csv(self):
        """Test exporting and importing contacts via CSV."""
        # Add some contacts
        for i, label in enumerate(["Alice", "Bob", "Charlie"]):
            wallet_history.add_contact(
                session_id=self.session_id,
                label=label,
                address=f"moon_{label}",
                category="friends" if i % 2 == 0 else "work",
                notes=f"Note for {label}",
            )

        # Export
        csv_data = wallet_history.export_address_book_csv(self.session_id)
        self.assertIn("Alice", csv_data)
        self.assertIn("Bob", csv_data)
        self.assertIn("Charlie", csv_data)

        # Import into new session
        session_2 = "test_import_session"
        result = wallet_history.import_address_book_csv(session_2, csv_data)
        self.assertEqual(result["imported"], 3)
        self.assertEqual(result["skipped"], 0)

        # Verify imported contacts
        contacts = wallet_history.get_contacts(session_2)
        self.assertEqual(len(contacts), 3)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
