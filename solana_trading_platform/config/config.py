# config/config.py
import os
from dotenv import load_dotenv
from config.schema import ConfigSchema
from core.logging import logger
from core.exceptions import TradingPlatformException

# Load variables from a .env file (place the file in your project root or config folder)
load_dotenv()

raw_config = {
    "SOLANA_RPC_URL": os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com"),
    "DATABASE_URL": os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/trading_db"),
    "MARKET_API_KEY": os.getenv("MARKET_API_KEY", "your_market_api_key")
}
# Validate configuration
try:
  config = ConfigSchema(**raw_config)
except Exception as e:
  logger.error(f"Exception loading config: {str(e)}")
  raise TradingPlatformException(f"Error loading config {str(e)}") from e