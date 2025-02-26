import json
import os
import logging
from solana.keypair import Keypair

logger = logging.getLogger(__name__)

class WalletManager:
    def __init__(self, wallet_path: str = None):
        self.wallet_path = wallet_path or os.getenv("SOLANA_WALLET_PATH")
        self.keypair = None

    def load_wallet(self):
        if not self.wallet_path or not os.path.exists(self.wallet_path):
            logger.error("Wallet path is not set or file does not exist.")
            raise FileNotFoundError("Wallet file not found.")
        with open(self.wallet_path, "r") as f:
            data = json.load(f)
        self.keypair = Keypair.from_secret_key(bytes(data))
        logger.info("Wallet loaded successfully.")
        return self.keypair
