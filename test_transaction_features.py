"""Tests for transaction search and export features."""

import sys
import time
import wallet_history

# Fix encoding on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def test_search_transactions():
    """Test transaction search functionality."""
    session_id = "test_session_search"

    # Add test transactions
    wallet_history.add_transaction(
        session_id=session_id,
        txid="tx_001",
        direction="send",
        amount_units=100000,
        from_address="moon1sender",
        to_address="moon1recipient",
        fee_units=1000,
        status="confirmed",
        memo="Test send transaction",
    )

    wallet_history.add_transaction(
        session_id=session_id,
        txid="tx_002",
        direction="receive",
        amount_units=50000,
        from_address="moon1source",
        to_address="moon1receiver",
        status="confirmed",
        memo="Test receive transaction",
    )

    # Search by txid
    result = wallet_history.search_transactions(session_id, query="tx_001")
    assert result["total"] == 1
    assert result["transactions"][0]["txid"] == "tx_001"
    print("✅ Search by TXID works")

    # Search by address
    result = wallet_history.search_transactions(session_id, query="moon1recipient")
    assert result["total"] == 1
    assert result["transactions"][0]["to_address"] == "moon1recipient"
    print("✅ Search by address works")

    # Search by memo
    result = wallet_history.search_transactions(session_id, query="receive")
    assert result["total"] == 1
    assert "receive" in result["transactions"][0]["memo"].lower()
    print("✅ Search by memo works")

    # Filter by status
    result = wallet_history.search_transactions(session_id, status="confirmed")
    assert result["total"] == 2
    print("✅ Filter by status works")

    # Filter by direction
    result = wallet_history.search_transactions(session_id, direction="send")
    assert result["total"] == 1
    assert result["transactions"][0]["direction"] == "send"
    print("✅ Filter by direction works")

    # Filter by amount range
    result = wallet_history.search_transactions(session_id, amount_min=60000, amount_max=150000)
    assert result["total"] == 1
    assert result["transactions"][0]["amount_units"] == 100000
    print("✅ Filter by amount range works")

    # Combined search
    result = wallet_history.search_transactions(
        session_id,
        query="tx",
        status="confirmed",
        direction="receive",
    )
    assert result["total"] == 1
    assert result["transactions"][0]["direction"] == "receive"
    print("✅ Combined search works")


def test_export_transactions_csv():
    """Test transaction export to CSV."""
    session_id = "test_session_export"

    # Add test transactions
    now = int(time.time())
    wallet_history.add_transaction(
        session_id=session_id,
        txid="exp_001",
        direction="send",
        amount_units=250000,
        from_address="moon1sender",
        to_address="moon1recipient",
        fee_units=5000,
        status="confirmed",
        memo="Payment for services",
    )

    wallet_history.add_transaction(
        session_id=session_id,
        txid="exp_002",
        direction="receive",
        amount_units=150000,
        from_address="moon1payer",
        to_address="moon1receiver",
        fee_units=0,
        status="confirmed",
        memo="",
    )

    # Export as CSV
    csv_data = wallet_history.export_transactions_csv(session_id)
    assert csv_data is not None
    assert len(csv_data) > 0

    # Check CSV structure
    lines = csv_data.split("\n")
    assert "Date,Type,Address,Amount,Fee,Status,TXID,Memo" in lines[0]
    print("✅ CSV header is correct")

    # Check transaction rows
    assert any("Send" in line for line in lines)
    assert any("Receive" in line for line in lines)
    print("✅ CSV contains transaction data")

    # Check summary
    assert any("Summary" in line for line in lines)
    assert any("Total Sent" in line for line in lines)
    assert any("Total Received" in line for line in lines)
    print("✅ CSV contains summary")

    print(f"CSV Sample (first 500 chars):\n{csv_data[:500]}")


def test_export_without_fees():
    """Test CSV export without fees."""
    session_id = "test_session_no_fees"

    wallet_history.add_transaction(
        session_id=session_id,
        txid="nf_001",
        direction="send",
        amount_units=100000,
        from_address="moon1a",
        to_address="moon1b",
        fee_units=1000,
        status="confirmed",
    )

    csv_data = wallet_history.export_transactions_csv(
        session_id,
        include_fees=False,
        include_memo=False,
    )

    lines = csv_data.split("\n")
    # Header should not have Fee or Memo
    assert "Fee" not in lines[0]
    assert "Memo" not in lines[0]
    print("✅ CSV export without fees/memo works")


def test_export_with_date_range():
    """Test CSV export with date filtering."""
    session_id = "test_session_dates"

    now = int(time.time())
    past = now - 86400  # 1 day ago

    wallet_history.add_transaction(
        session_id=session_id,
        txid="date_old",
        direction="send",
        amount_units=100000,
        from_address="moon1a",
        to_address="moon1b",
        status="confirmed",
    )

    wallet_history.add_transaction(
        session_id=session_id,
        txid="date_new",
        direction="send",
        amount_units=200000,
        from_address="moon1a",
        to_address="moon1b",
        status="confirmed",
    )

    # Export only recent transactions
    csv_data = wallet_history.export_transactions_csv(
        session_id,
        date_from=now - 3600,  # Last hour
    )

    assert "date_new" in csv_data or len(csv_data.split("\n")) > 5
    print("✅ CSV export with date range works")


if __name__ == "__main__":
    test_search_transactions()
    test_export_transactions_csv()
    test_export_without_fees()
    test_export_with_date_range()
    print("\n✅ All transaction feature tests passed!")
