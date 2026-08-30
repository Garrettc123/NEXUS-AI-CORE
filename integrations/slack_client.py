"""
integrations/slack_client.py

Slack client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Post messages & rich Block Kit payloads to any channel
  - Revenue alerts (formatted)
  - Error / system alerts
  - Incoming webhook fallback
  - Signing secret verification
"""

import hashlib
import hmac
import logging
import time
from typing import Any, Optional

import httpx

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


class SlackClient:
    """Authenticated Slack Web API + webhook client."""

    def __init__(self):
        self._bot_token = require_secret(SecretKey.SLACK_BOT_TOKEN)
        self._signing_secret = get_secret(SecretKey.SLACK_SIGNING_SECRET)
        self._webhook_url = get_secret(SecretKey.SLACK_WEBHOOK_URL)
        self._channel_alerts = get_secret(SecretKey.SLACK_CHANNEL_ALERTS, "#alerts")
        self._channel_revenue = get_secret(SecretKey.SLACK_CHANNEL_REVENUE, "#revenue")
        self._headers = {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        logger.info("[Slack] Client initialised")

    # ── Messaging ──────────────────────────────────────────────────────────

    def post(self, channel: str, text: str, blocks: list | None = None) -> dict:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        r = httpx.post(f"{SLACK_API}/chat.postMessage", headers=self._headers, json=payload, timeout=10)
        data = r.json()
        if not data.get("ok"):
            logger.error("[Slack] post failed: %s", data.get("error"))
        return data

    def alert(self, message: str, level: str = "info") -> dict:
        """Post a system alert to the alerts channel."""
        emoji = {"info": ":information_source:", "warn": ":warning:", "error": ":rotating_light:", "success": ":white_check_mark:"}.get(level, ":speech_balloon:")
        return self.post(self._channel_alerts, f"{emoji} {message}")

    def revenue_alert(self, amount: float, currency: str, source: str, description: str = "") -> dict:
        """Post a revenue event to the revenue channel with Block Kit formatting."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f":moneybag: Revenue Event — {source}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Amount:*\n`{currency} {amount:,.2f}`"},
                {"type": "mrkdwn", "text": f"*Source:*\n{source}"},
            ]},
        ]
        if description:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": description}})
        return self.post(self._channel_revenue, f":moneybag: {currency} {amount:,.2f} from {source}", blocks=blocks)

    def webhook_post(self, text: str) -> bool:
        """Post via incoming webhook (no token needed)."""
        if not self._webhook_url:
            logger.warning("[Slack] Webhook URL not configured")
            return False
        r = httpx.post(self._webhook_url, json={"text": text}, timeout=10)
        return r.status_code == 200

    # ── Verification ───────────────────────────────────────────────────────

    def verify_signature(self, body: bytes, timestamp: str, signature: str) -> bool:
        if not self._signing_secret:
            return False
        if abs(time.time() - float(timestamp)) > 300:
            return False
        basestring = f"v0:{timestamp}:{body.decode()}"
        computed = "v0=" + hmac.new(self._signing_secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature)
