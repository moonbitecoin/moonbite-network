"""Tests for price_feed module."""

import sys
import time
import price_feed

# Fix encoding on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def test_get_price():
    """Test price fetching."""
    price_feed.clear_cache()

    price = price_feed.get_price()
    assert price is not None
    assert "price_usd" in price
    assert "change_24h" in price
    assert "high_24h" in price
    assert "low_24h" in price
    assert "market_cap" in price
    assert "volume_24h" in price
    assert "timestamp" in price

    assert price["price_usd"] > 0
    print(f"✅ Price: ${price['price_usd']:.2f}, 24h Change: {price['change_24h']:.2f}%")


def test_price_caching():
    """Test that price is cached."""
    price_feed.clear_cache()

    # First call
    price1 = price_feed.get_price()
    ts1 = price1["timestamp"]

    # Sleep a tiny bit and fetch again
    time.sleep(0.1)
    price2 = price_feed.get_price()

    # Should be the same timestamp (cached)
    assert price1["timestamp"] == price2["timestamp"]
    print(f"✅ Cache working: both calls returned timestamp {ts1}")


def test_price_history():
    """Test price history."""
    history = price_feed.get_price_history(hours=24)

    assert history is not None
    assert "prices" in history
    assert len(history["prices"]) == 24
    assert history["count"] == 24

    # Check structure
    for point in history["prices"]:
        assert "timestamp" in point
        assert "price_usd" in point
        assert point["price_usd"] > 0

    print(f"✅ Price history: {len(history['prices'])} data points")


def test_price_history_different_hours():
    """Test price history with different hour ranges."""
    for hours in [1, 6, 12, 48, 720]:
        history = price_feed.get_price_history(hours=hours)
        assert len(history["prices"]) == hours
        print(f"✅ Price history for {hours}h: {len(history['prices'])} data points")


if __name__ == "__main__":
    test_get_price()
    test_price_caching()
    test_price_history()
    test_price_history_different_hours()
    print("\n✅ All price_feed tests passed!")
