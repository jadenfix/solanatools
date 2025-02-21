# config/schema.py
from pydantic import BaseModel

class ConfigSchema(BaseModel):
    SOLANA_RPC_URL: str
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/trading_db"
    MARKET_API_KEY: str = "your_market_api_key"