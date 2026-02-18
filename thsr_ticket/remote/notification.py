import requests
import logging

logger = logging.getLogger(__name__)

class Notification:
    def __init__(self, config: dict):
        self.config = config.get("notification", {})
        self.webhook_url = self.config.get("webhook_url")

    def send(self, message: str, level: str = "INFO"):
        """
        Send notification via configured channels.
        """
        # Always log to stdout
        if level == "ERROR":
            logger.error(message)
        else:
            logger.info(message) # Stdout is handled by basicConfig

        # Webhook (Slack/Line/Discord compatible)
        if self.webhook_url:
            try:
                payload = {"text": f"[{level}] {message}"}
                # Slack expects 'text', Discord 'content'. Let's support generic JSON.
                requests.post(self.webhook_url, json=payload, timeout=5)
            except Exception as e:
                logger.warning(f"Failed to send webhook notification: {e}")
