import asyncio
import logging

logger = logging.getLogger(__name__)

class RealtimeDataFeed:
    def __init__(self, ws_endpoint: str):
        self.ws_endpoint = ws_endpoint

    async def stream(self):
        while True:
            try:
                data_point = await self._fetch_data()
                yield data_point
            except Exception as e:
                logger.error(f"Realtime data error: {e}")
                await asyncio.sleep(1)

    async def _fetch_data(self):
        await asyncio.sleep(0.1)
        return {"price": 100.0, "timestamp": asyncio.get_event_loop().time()}
