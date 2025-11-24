import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def send_slack_alert(webhook_url: Optional[str], message: str) -> None:
    """Send a message to Slack webhook; swallow errors to avoid crashing trading loop."""
    if not webhook_url:
        return
    try:
        resp = requests.post(webhook_url, json={"text": message}, timeout=3)
        if resp.status_code >= 400:
            logger.warning("Slack alert failed with status %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Failed to send Slack alert")


def send_telegram_alert(bot_token: Optional[str], chat_id: Optional[str], message: str) -> None:
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=3)
        if resp.status_code >= 400:
            logger.warning("Telegram alert failed with status %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Failed to send Telegram alert")
