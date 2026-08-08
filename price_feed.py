"""MoonBite price feed module — real-time price tracking with caching.

Fetches MBITE price from configured exchange (or uses hardcoded demo price).
Cache with 15-minute TTL to minimize external API calls.
"""

from __future__ import annotations

import json
import time
from typing import Optional

_CACHE = {
    "data": None,
    "timestamp": 0,
}
_CACHE_TTL = 15 * 60  # 15 minutes


def _get_demo_price() -> dict:
    """Return demo price data for testing (no external API required)."""
    return {
        "price_usd": 45.67,
        "change_24h": 2.5,
        "high_24h": 48.32,
        "low_24h": 43.21,
        "market_cap": 9134000000,
        "volume_24h": 45600000,
        "timestamp": int(time.time()),
    }


def _fetch_from_exchange() -> Optional[dict]:
    """Fetch price from configured exchange (CoinGecko, Kraken, etc).

    Implement actual exchange API call here. For now returns None to fall back
    to demo price.

    Returns:
        dict with price data, or None if fetch fails
    """
    # TODO: Implement actual exchange API integration
    # Example: CoinGecko API
    # try:
    #     import requests
    #     resp = requests.get(
    #         "https://api.coingecko.com/api/v3/simple/price",
    #         params={"ids": "moonbite", "vs_currencies": "usd", "include_market_cap": "true", "include_24h_vol": "true", "include_24h_change": "true"},
    #         timeout=5
    #     )
    #     data = resp.json().get("moonbite", {})
    #     return {
    #         "price_usd": data.get("usd", 0),
    #         "change_24h": data.get("usd_24h_change", 0),
    #         "market_cap": data.get("usd_market_cap", 0),
    #         "volume_24h": data.get("usd_24h_vol", 0),
    #         "timestamp": int(time.time()),
    #     }
    # except Exception as e:
    #     print(f"[price_feed] Exchange fetch error: {e}")
    #     return None
    return None


def get_price() -> dict:
    """Get current MBITE price with caching.

    Returns:
        dict with price_usd, change_24h, high_24h, low_24h, market_cap, volume_24h, timestamp
    """
    now = int(time.time())

    # Check cache validity (TTL check)
    if _CACHE["data"] and (now - _CACHE["timestamp"]) < _CACHE_TTL:
        return _CACHE["data"]

    # Try to fetch from exchange
    price_data = _fetch_from_exchange()

    # Fall back to demo price if exchange fetch fails or returns None
    if not price_data:
        price_data = _get_demo_price()

    # Update cache
    _CACHE["data"] = price_data
    _CACHE["timestamp"] = now

    return price_data


def get_price_history(hours: int = 24) -> dict:
    """Get price history for the past N hours.

    Args:
        hours: Number of hours to retrieve (default 24)

    Returns:
        dict with 'prices' list of {"timestamp", "price_usd"} and metadata
    """
    now = int(time.time())

    # TODO: Implement actual price history fetching from exchange
    # For now, return synthetic 24h history based on current price with small variations
    current_price = get_price()
    base_price = current_price["price_usd"]

    prices = []
    for i in range(hours):
        # Simple sine wave for demo
        variation = base_price * 0.03 * (0.5 + 0.5 * ((i / hours) - 0.5))
        price_point = base_price - variation
        timestamp = now - ((hours - i) * 3600)
        prices.append({
            "timestamp": timestamp,
            "price_usd": round(price_point, 2),
        })

    return {
        "prices": prices,
        "count": len(prices),
        "start_timestamp": prices[0]["timestamp"] if prices else now,
        "end_timestamp": prices[-1]["timestamp"] if prices else now,
    }


def clear_cache():
    """Manually clear the price cache (for testing)."""
    global _CACHE
    _CACHE = {"data": None, "timestamp": 0}
