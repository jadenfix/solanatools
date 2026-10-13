"""Spot paper execution. SHORT signals close inventory; no borrowing or RPC."""
from math import isfinite


class PaperExecutionEngine:
    def __init__(self, strategy, cash=10000.0, max_exposure=0.25,
                 fee_bps=10.0, stop_loss_pct=0.05, take_profit_pct=0.10):
        values = (cash, max_exposure, fee_bps, stop_loss_pct, take_profit_pct)
        if not all(isfinite(value) for value in values):
            raise ValueError("configuration must be finite")
        if cash <= 0 or not 0 < max_exposure <= 1 or not 0 <= fee_bps < 10000:
            raise ValueError("invalid cash, exposure, or fee")
        if not 0 < stop_loss_pct < 1 or take_profit_pct <= 0:
            raise ValueError("invalid exit thresholds")
        self.strategy = strategy
        self.initial_cash = self.cash = cash
        self.max_exposure = max_exposure
        self.fee = fee_bps / 10000
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.quantity = 0.0
        self.entry_price = None
        self.ledger = []
        self.curve = []

    def _buy(self, price, timestamp):
        # Target exposure includes fees so a purchase cannot overdraw cash.
        spend = min(self.cash, self.cash * self.max_exposure)
        quantity = spend / (price * (1 + self.fee))
        self.cash -= spend
        self.quantity = quantity
        self.entry_price = price
        self.ledger.append({"timestamp": timestamp, "side": "BUY", "reason": "RSI",
                            "price": price, "quantity": quantity,
                            "fee": quantity * price * self.fee, "cash": self.cash})

    def _sell(self, price, timestamp, reason):
        proceeds = self.quantity * price
        fee = proceeds * self.fee
        self.cash += proceeds - fee
        self.ledger.append({"timestamp": timestamp, "side": "SELL", "reason": reason,
                            "price": price, "quantity": self.quantity,
                            "fee": fee, "cash": self.cash})
        self.quantity = 0.0
        self.entry_price = None

    def run(self, data):
        if self.curve:
            raise RuntimeError("create a new engine for each replay")
        for index, point in enumerate(data):
            price = float(point["price"])
            if not isfinite(price) or price <= 0:
                raise ValueError(f"invalid price at row {index + 1}")
            timestamp = point.get("timestamp", index)
            exited = False
            if self.quantity:
                if price <= self.entry_price * (1 - self.stop_loss_pct):
                    self._sell(price, timestamp, "STOP_LOSS")
                    exited = True
                elif price >= self.entry_price * (1 + self.take_profit_pct):
                    self._sell(price, timestamp, "TAKE_PROFIT")
                    exited = True
            self.strategy.next({"price": price, "timestamp": timestamp})
            for signal in self.strategy.get_signals():
                if signal["direction"] == "LONG" and not self.quantity and not exited:
                    self._buy(price, timestamp)
                elif signal["direction"] == "SHORT" and self.quantity:
                    self._sell(price, timestamp, "RSI")
            equity = self.cash + self.quantity * price
            self.curve.append({"timestamp": timestamp, "price": price, "cash": self.cash,
                               "quantity": self.quantity, "equity": equity,
                               "rsi": self.strategy.last_rsi})
        if not self.curve:
            raise ValueError("replay requires at least one price")
        peak = self.initial_cash
        max_drawdown = 0.0
        for point in self.curve:
            peak = max(peak, point["equity"])
            max_drawdown = max(max_drawdown, 1 - point["equity"] / peak)
        return {"mode": "offline-paper", "bars": len(self.curve),
                "initial_equity": self.initial_cash, "final_equity": self.curve[-1]["equity"],
                "return_pct": 100 * (self.curve[-1]["equity"] / self.initial_cash - 1),
                "max_drawdown_pct": 100 * max_drawdown,
                "fills": len(self.ledger), "ledger": self.ledger, "curve": self.curve}
