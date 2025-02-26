from solana.transaction import Transaction
from solana.rpc.types import TxOpts
from solders.message import Message
from solana.keypair import Keypair
import asyncio
import logging
import solana.system_program as system_program
from solana.system_program import SYS_PROGRAM_ID

logger = logging.getLogger(__name__)

class TransactionBuilder:
    def __init__(self, fee_estimator):
        self.fee_estimator = fee_estimator
        self.recent_blockhash = None
        self.priority_fee = 0
        
    async def build(self, instructions, signer: Keypair):
        if not self.recent_blockhash:
            self.recent_blockhash = await self.fee_estimator.get_recent_blockhash()
        self.priority_fee = await self.fee_estimator.calculate_priority_fee()
        # Example: Add a dummy priority fee instruction (update with your logic)
        instructions.append(
            system_program.transfer(SYS_PROGRAM_ID, signer.pubkey(), signer.pubkey(), self.priority_fee)
        )
        message = Message.new_with_blockhash(
            instructions,
            signer.pubkey(),
            self.recent_blockhash
        )
        return Transaction([signer], message, self.recent_blockhash)
