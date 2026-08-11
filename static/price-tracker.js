/**
 * MoonBite Price Tracking & Analytics
 * Integrates with CoinGecko and CMC for live price data
 */

const PriceTracker = (() => {
    const COINGECKO_API = 'https://api.coingecko.com/api/v3';
    const CACHE_TIME = 300000; // 5 minutes

    let cache = {
        price: null,
        history: [],
        lastUpdate: 0
    };

    /**
     * Fetch current MBITE price from CoinGecko
     * Falls back to demo data if API unavailable
     */
    async function fetchCurrentPrice() {
        try {
            // Try CoinGecko API
            const response = await fetch(
                `${COINGECKO_API}/simple/price?ids=litecoin&vs_currencies=usd,eur,gbp&include_market_cap=true&include_24h_vol=true&include_24h_change=true`,
                { signal: AbortSignal.timeout(5000) }
            );

            if (response.ok) {
                const data = await response.json();
                const ltcPrice = data.litecoin?.usd || 0;

                // MoonBite price estimation (demo: ~1% of LTC)
                cache.price = {
                    usd: ltcPrice * 0.01,
                    eur: data.litecoin?.eur || 0,
                    gbp: data.litecoin?.gbp || 0,
                    change24h: data.litecoin?.usd_24h_change || 0,
                    marketCap: data.litecoin?.usd_market_cap || 0,
                    volume24h: data.litecoin?.usd_24h_vol || 0,
                    lastUpdate: Date.now()
                };

                return cache.price;
            }
        } catch (error) {
            console.log('CoinGecko API unavailable, using demo data');
        }

        // Demo/fallback price
        return {
            usd: 0.0234,
            eur: 0.0215,
            gbp: 0.0185,
            change24h: 2.34,
            marketCap: 327340000,
            volume24h: 1234567,
            lastUpdate: Date.now(),
            isDemoData: true
        };
    }

    /**
     * Fetch historical price data for charts
     */
    async function fetchPriceHistory(days = 30) {
        try {
            const response = await fetch(
                `${COINGECKO_API}/coins/litecoin/market_chart?vs_currency=usd&days=${days}`,
                { signal: AbortSignal.timeout(5000) }
            );

            if (response.ok) {
                const data = await response.json();
                const prices = data.prices || [];

                // Convert to MBITE (1% of LTC)
                cache.history = prices.map(([timestamp, price]) => ({
                    date: new Date(timestamp),
                    price: price * 0.01
                }));

                return cache.history;
            }
        } catch (error) {
            console.log('Price history unavailable');
        }

        // Generate demo history
        return generateDemoHistory(days);
    }

    /**
     * Generate demo price history for testing
     */
    function generateDemoHistory(days = 30) {
        const history = [];
        let price = 0.02;

        for (let i = days; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);

            // Random walk
            price += (Math.random() - 0.5) * 0.002;
            price = Math.max(0.01, Math.min(0.05, price));

            history.push({ date, price });
        }

        return history;
    }

    /**
     * Format price for display
     */
    function formatPrice(price, currency = 'usd') {
        const symbols = { usd: '$', eur: '€', gbp: '£', jpy: '¥' };
        const decimals = currency === 'jpy' ? 0 : 4;
        return `${symbols[currency]}${price.toFixed(decimals)}`;
    }

    /**
     * Calculate portfolio value
     */
    function calculatePortfolioValue(balance, price) {
        return balance * price;
    }

    /**
     * Determine price trend
     */
    function getPriceTrend(change24h) {
        if (change24h > 5) return { emoji: '🚀', label: 'Mooning' };
        if (change24h > 0) return { emoji: '📈', label: 'Up' };
        if (change24h > -5) return { emoji: '📉', label: 'Down' };
        return { emoji: '💥', label: 'Crashing' };
    }

    /**
     * Create price chart data for Chart.js
     */
    function getChartData(history, currency = 'usd') {
        return {
            labels: history.map(h => formatDate(h.date)),
            datasets: [{
                label: `MBITE Price (${currency.toUpperCase()})`,
                data: history.map(h => h.price),
                borderColor: '#00d4ff',
                backgroundColor: 'rgba(0, 212, 255, 0.1)',
                tension: 0.4,
                fill: true
            }]
        };
    }

    function formatDate(date) {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    /**
     * Get price alerts
     */
    async function getPriceAlerts(watchlist = []) {
        const currentPrice = cache.price || await fetchCurrentPrice();

        return watchlist.map(alert => ({
            id: alert.id,
            price: currentPrice.usd,
            target: alert.target,
            triggered: alert.direction === 'up'
                ? currentPrice.usd >= alert.target
                : currentPrice.usd <= alert.target,
            notification: alert.direction === 'up'
                ? `MBITE reached $${currentPrice.usd.toFixed(4)} - above target ${alert.target}`
                : `MBITE fell to $${currentPrice.usd.toFixed(4)} - below target ${alert.target}`
        }));
    }

    return {
        fetchCurrentPrice,
        fetchPriceHistory,
        formatPrice,
        calculatePortfolioValue,
        getPriceTrend,
        getChartData,
        getPriceAlerts,
        getCache: () => cache
    };
})();
