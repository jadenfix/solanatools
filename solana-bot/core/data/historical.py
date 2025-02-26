import pandas as pd
import logging

logger = logging.getLogger(__name__)

class HistoricalDataLoader:
    def __init__(self, source_url: str):
        self.source_url = source_url
        self.cached_data = None

    def load_data(self):
        try:
            self.cached_data = pd.read_csv(self.source_url)
            logger.info("Historical data loaded.")
        except Exception as e:
            logger.error(f"Failed to load historical data: {e}")
        return self.cached_data
