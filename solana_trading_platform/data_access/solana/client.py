# data_access/solana/client.py
import solana.rpc.api
import config
import core
from solana.rpc.api import Client
#from config.config import config
from core.logging import logger
from core.constants import LAMPORTS_PER_SOL
from core.event_bus import EventBus

class SolanaClient:
    def __init__(self):
        self.client = Client(config.SOLANA_RPC_URL)
        self.event_bus = EventBus()  # Instantiate event bus
        logger.info(f"Connected to Solana RPC at {config.SOLANA_RPC_URL}")

    def get_account_balance(self, public_key: str) -> float:
        """Fetch the SOL balance for a given public key."""
        try:
            response = self.client.get_balance(public_key)
            if "result" in response and response["result"] is not None:
                balance_lamports = response["result"]["value"]
                balance_sol = balance_lamports / LAMPORTS_PER_SOL
                logger.info(f"Account {public_key} balance: {balance_sol} SOL")
                self.event_bus.publish("balance_fetched", {"public_key": public_key, "balance": balance_sol})
                return balance_sol
            else:
                logger.error(f"Error fetching balance for {public_key}: {response}")
                return 0.0
        except Exception as e:
            logger.error(f"Exception in get_account_balance: {str(e)}")
            return 0.0

# For testing purposes:
if __name__ == "__main__":
    sol_client = SolanaClient()
    test_pubkey = "YourTestPublicKeyHere"  # Replace with a valid public key for testing
    balance = sol_client.get_account_balance(test_pubkey)
    print(f"Balance: {balance} SOL")