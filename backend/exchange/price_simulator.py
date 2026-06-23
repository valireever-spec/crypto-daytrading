"""Mock price simulator for demonstration when Binance WebSocket data unavailable."""

import random
import asyncio
from datetime import datetime
from typing import Dict

# Realistic base prices (as of June 23, 2026)
BASE_PRICES = {
    'BTCUSDT': 62322.62,
    'ETHUSDT': 1658.69,
    'BNBUSDT': 574.64,
}

# Volatility per symbol (% change per tick)
VOLATILITY = {
    'BTCUSDT': 0.15,  # Bitcoin: 0.15% per tick
    'ETHUSDT': 0.12,  # Ethereum: 0.12% per tick
    'BNBUSDT': 0.10,  # BNB: 0.10% per tick
}


class PriceSimulator:
    """Simulates realistic crypto price movements for demo purposes."""

    def __init__(self):
        self.prices = dict(BASE_PRICES)
        self.last_update = {}

    def get_prices(self) -> Dict[str, float]:
        """Get current simulated prices."""
        return dict(self.prices)

    def get_price(self, symbol: str) -> float:
        """Get price for a single symbol."""
        return self.prices.get(symbol, 0.0)

    def update(self):
        """Simulate price movement (random walk)."""
        for symbol, base_price in BASE_PRICES.items():
            if symbol not in self.prices:
                self.prices[symbol] = base_price

            # Random walk: ±volatility %
            volatility = VOLATILITY.get(symbol, 0.1)
            change_pct = random.uniform(-volatility, volatility) / 100
            new_price = self.prices[symbol] * (1 + change_pct)

            # Keep price realistic (no negative, no extreme moves)
            new_price = max(new_price, base_price * 0.9)
            new_price = min(new_price, base_price * 1.1)

            self.prices[symbol] = new_price
            self.last_update[symbol] = datetime.utcnow()

    async def run_simulation(self, interval: int = 3):
        """Run continuous price simulation."""
        while True:
            self.update()
            await asyncio.sleep(interval)


# Global simulator instance
_simulator = None


def init_simulator():
    """Initialize the price simulator."""
    global _simulator
    _simulator = PriceSimulator()
    return _simulator


def get_simulator() -> PriceSimulator:
    """Get the price simulator instance."""
    return _simulator


def inject_prices_to_stream(stream_client):
    """Inject simulated prices into the stream client's cache."""
    if _simulator is None:
        return

    prices = _simulator.get_prices()
    for symbol, price in prices.items():
        stream_client.price_cache[symbol] = price
        from datetime import datetime
        stream_client.last_update[symbol] = datetime.utcnow()
