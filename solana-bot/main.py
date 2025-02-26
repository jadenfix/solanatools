import asyncio
import logging
from core.strategies.rsi_momentum import RSIMomentumStrategy
from core.data.realtime import RealtimeDataFeed
from core.engine.execution import LiveExecutionEngine

logging.basicConfig(level=logging.INFO)

async def main():
    strategy = RSIMomentumStrategy()
    data_feed = RealtimeDataFeed("wss://api.mainnet-beta.solana.com")
    engine = LiveExecutionEngine(strategy, data_feed)
    await engine.run()

if __name__ == "__main__":
    asyncio.run(main())
