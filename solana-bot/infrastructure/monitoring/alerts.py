import logging
import requests

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def send_alert(self, message: str):
        logger.info(f"Sending alert: {message}")
        if self.webhook_url:
            try:
                response = requests.post(self.webhook_url, json={"text": message})
                if response.status_code != 200:
                    logger.error("Failed to send alert.")
            except Exception as e:
                logger.error(f"Alert error: {e}")
        else:
            logger.warning("No webhook URL configured for alerts.")
