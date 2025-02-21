# core/logging.py
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

setup_logging()
logger = logging.getLogger("solana_trading_platform")