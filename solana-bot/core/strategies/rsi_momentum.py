"""Rolling RSI signals with bounded memory and explicit price validation."""
from collections import deque
from math import isfinite
from core.strategies.base import BaseStrategy


class RSIMomentumStrategy(BaseStrategy):
    def __init__(self, period=14, overbought=70, oversold=30):
        super().__init__()
        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")
        if not 0 <= oversold < overbought <= 100:
            raise ValueError("require 0 <= oversold < overbought <= 100")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self.prices = deque(maxlen=period + 1)
        self.last_rsi = None

    def next(self, data_point):
        price = float(data_point["price"])
        if not isfinite(price) or price <= 0:
            raise ValueError("price must be finite and positive")
        self.prices.append(price)
        if len(self.prices) < self.period + 1:
            return
        prices = list(self.prices)
        deltas = [b - a for a, b in zip(prices, prices[1:])]
        gain = sum(max(delta, 0) for delta in deltas)
        loss = sum(max(-delta, 0) for delta in deltas)
        self.last_rsi = 100 * gain / (gain + loss) if gain + loss else 50.0
        if self.last_rsi > self.overbought:
            self.signals.append({"direction": "SHORT", "price": price})
        elif self.last_rsi < self.oversold:
            self.signals.append({"direction": "LONG", "price": price})
