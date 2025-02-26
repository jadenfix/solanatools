import numpy as np
from core.strategies.base import BaseStrategy

class RSIMomentumStrategy(BaseStrategy):
    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        super().__init__()
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self.prices = []

    def next(self, data_point: dict):
        price = data_point.get("price")
        self.prices.append(price)
        if len(self.prices) > self.period:
            deltas = np.diff(self.prices[-self.period:])
            gain = sum(delta for delta in deltas if delta > 0)
            loss = -sum(delta for delta in deltas if delta < 0)
            rsi = 100 * gain / (gain + loss) if (gain + loss) > 0 else 50
            self.log(f"RSI computed: {rsi:.2f}")
            if rsi > self.overbought:
                self.signals.append({"direction": "SHORT", "price": price})
            elif rsi < self.oversold:
                self.signals.append({"direction": "LONG", "price": price})
