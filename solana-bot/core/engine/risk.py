import logging

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, max_exposure: float, stop_loss_pct: float, take_profit_pct: float):
        self.max_exposure = max_exposure      # e.g., maximum percentage of portfolio per trade
        self.stop_loss_pct = stop_loss_pct    # e.g., 0.05 for 5% stop loss
        self.take_profit_pct = take_profit_pct  # e.g., 0.10 for 10% profit target

    def validate_order(self, order, current_exposure: float) -> bool:
        projected_exposure = current_exposure + order.get('amount', 0)
        if projected_exposure > self.max_exposure:
            logger.warning("RiskManager: Order exceeds max exposure.")
            return False
        return True

    def evaluate_exit(self, entry_price: float, current_price: float):
        if current_price <= entry_price * (1 - self.stop_loss_pct):
            return 'STOP_LOSS'
        elif current_price >= entry_price * (1 + self.take_profit_pct):
            return 'TAKE_PROFIT'
        return None
