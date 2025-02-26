import asyncio
import logging
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solders.signature import Signature
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from solana.publickey import PublicKey
from typing import Optional, List

logger = logging.getLogger(__name__)

class EnhancedSolanaClient:
    def __init__(self, rpc_urls: List[str]):
        self.clients = [AsyncClient(url) for url in rpc_urls]
        self.current_client = 0
        self.commitment = Confirmed
        
    async def rotate_client(self):
        self.current_client = (self.current_client + 1) % len(self.clients)
        
    async def send_transaction(
        self, 
        txn: Transaction,
        skip_preflight: bool = False,
        max_retries: int = 3
    ) -> Optional[Signature]:
        for _ in range(max_retries):
            try:
                client = self.clients[self.current_client]
                result = await client.send_transaction(
                    txn,
                    opts=TxOpts(
                        skip_preflight=skip_preflight,
                        preflight_commitment=self.commitment
                    )
                )
                return result.value
            except Exception as e:
                logger.error(f"Transaction failed: {str(e)}")
                await self.rotate_client()
        return None

    async def get_multiple_accounts(self, pubkeys: List[PublicKey]):
        return await asyncio.gather(
            *[self.clients[self.current_client].get_account_info(pk) for pk in pubkeys]
        )
