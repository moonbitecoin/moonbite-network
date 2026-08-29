/* MoonBite price tracker — reports that there is no price.
 *
 * This file previously fetched LITECOIN's price from the CoinGecko API and
 * multiplied it by 0.01 to invent a MoonBite figure, falling back to a
 * hardcoded $0.0234. Two separate problems:
 *
 *   1. MBITE is not listed anywhere and has no market price. A number derived
 *      from a different asset is a fabrication, not an estimate.
 *   2. The CoinGecko call was a third-party request from the visitor's
 *      browser, which contradicts /privacy — that page states this site loads
 *      nothing that phones home.
 *
 * So this module makes no network request and returns an explicit unpriced
 * result. When MBITE is genuinely listed, point fetchPrice() at the real venue
 * through our own origin (never a third party directly from the browser).
 */
(function (global) {
  'use strict';

  var UNPRICED = {
    listed: false,
    usd: null,          // null, not 0 — "$0.00" reads as a price of zero
    eur: null,
    gbp: null,
    change24h: null,
    marketCap: null,
    volume24h: null,
    message: 'MBITE has no market price. It is not listed on any exchange ' +
             'and is not an investment or a security.'
  };

  function fetchPrice() {
    return Promise.resolve(Object.assign({ lastUpdate: Date.now() }, UNPRICED));
  }

  function fetchHistory() {
    // A synthesized series would render as a chart indistinguishable from real
    // market data for an asset that has never traded.
    return Promise.resolve({ listed: false, points: [], message: UNPRICED.message });
  }

  /* Render helper: anything showing a value should show this instead of a
     currency amount, so no surface can accidentally print a fake number. */
  function formatPrice() {
    return 'Not listed';
  }

  global.MoonBitePrice = {
    fetchPrice: fetchPrice,
    fetchHistory: fetchHistory,
    formatPrice: formatPrice,
    UNPRICED: UNPRICED
  };
})(typeof window !== 'undefined' ? window : this);
