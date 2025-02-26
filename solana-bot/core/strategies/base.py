import logging

logger = logging.getLogger(__name__)

class BaseStrategy:
    def __init__(self):
        self.signals = []
        self.positions = {}

    def next(self, data_point: dict):
        raise NotImplementedError

    def get_signals(self):
        signals = self.signals.copy()
        self.signals.clear()
        return signals

    def log(self, message: str):
        logger.info(f"Strategy Log: {message}")
