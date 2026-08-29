"""MoonBite price feed — deliberately reports "no price".

MBITE is not listed on any exchange and has no market price. This module used
to fabricate one: a hardcoded $45.67 with a $9.13bn market cap, served from
live, unauthenticated endpoints. That is not a placeholder, it is a false
statement about a financial asset, and it contradicted every other surface on
the site (/privacy, the footer strip, /free) which say plainly that MBITE has
no market value and is not an investment.

So the module now returns an explicit "unpriced" answer instead of a number.
When MBITE is genuinely listed, implement `_fetch_from_exchange()` against the
real venue and the rest of this file starts working with no other change — but
until a real quote exists, the honest output is no quote at all.

Callers should branch on `listed`, never assume a numeric price is present.
"""

from __future__ import annotations

import time
from typing import Optional

_CACHE = {
    "data": None,
    "timestamp": 0,
}
_CACHE_TTL = 15 * 60  # 15 minutes


def _unpriced() -> dict:
    """The truthful response while MBITE has no market.

    Every numeric field is None rather than 0: a zero would render as "$0.00"
    and read as a price of zero, which is just as wrong as $45.67.
    """
    return {
        "listed": False,
        "price_usd": None,
        "change_24h": None,
        "high_24h": None,
        "low_24h": None,
        "market_cap": None,
        "volume_24h": None,
        "message": (
            "MBITE has no market price. It is not listed on any exchange and "
            "is not an investment or a security."
        ),
        "timestamp": int(time.time()),
    }


def _fetch_from_exchange() -> Optional[dict]:
    """Fetch a real quote from a real venue once MBITE is listed.

    Returns None while unlisted. Implement this against the actual exchange
    API when a listing exists, and return a dict shaped like _unpriced() with
    `listed` True and real numbers. Do not reintroduce a fallback constant:
    if the venue is unreachable, "unknown" is the correct answer.
    """
    return None


def get_price() -> dict:
    """Current MBITE price, or an explicit unpriced response.

    Cached for 15 minutes so a future real feed does not get hammered.
    """
    now = int(time.time())
    if _CACHE["data"] and (now - _CACHE["timestamp"]) < _CACHE_TTL:
        return _CACHE["data"]

    price_data = _fetch_from_exchange() or _unpriced()
    _CACHE["data"] = price_data
    _CACHE["timestamp"] = now
    return price_data


def get_price_history(hours: int = 24) -> dict:
    """Price history. Empty while unlisted — a synthesized series is a lie.

    The previous implementation generated points from a hash of the index,
    producing a chart that looked like real market data and was not.
    """
    return {
        "listed": False,
        "hours": max(1, min(int(hours or 24), 24 * 365)),
        "points": [],
        "message": "MBITE has no trading history. It is not listed on any exchange.",
        "timestamp": int(time.time()),
    }
