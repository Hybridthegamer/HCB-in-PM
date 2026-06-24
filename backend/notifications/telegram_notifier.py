"""Telegram Bot API notifications for HCB alerts."""
from __future__ import annotations

import httpx
import structlog

from config import settings

log = structlog.get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """Sends alert messages to a Telegram chat via the Bot API."""

    def __init__(self) -> None:
        self._enabled = bool(
            settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID
        )
        if not self._enabled:
            log.warning(
                "telegram_notifier_disabled",
                reason="Bot token or chat ID not configured",
            )

    async def send_alert(self, alert, rule, wallet) -> None:
        if not self._enabled:
            return

        text = self._build_message(alert, rule, wallet)
        url = (
            f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        )
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            log.info("telegram_sent", rule=rule.rule_name)
        except Exception as exc:
            log.error("telegram_send_failed", error=str(exc))
            raise

    def _build_message(self, alert, rule, wallet) -> str:
        ts = alert.dispatched_at.strftime("%Y-%m-%d %H:%M UTC")
        cbs = f"{alert.composite_score:.4f}" if alert.composite_score is not None else "N/A"
        metric_val = (
            f"{alert.triggered_metric:.4f}"
            if alert.triggered_metric is not None
            else "N/A"
        )
        short_wallet = wallet.wallet_id[:10] + "..." + wallet.wallet_id[-6:]
        return (
            f"<b>HCB Monitor Alert</b>\n"
            f"Rule: <b>{rule.rule_name}</b>\n"
            f"Wallet: <code>{short_wallet}</code>\n"
            f"Condition: {rule.metric} {rule.operator} {rule.threshold}\n"
            f"Triggered value: <b>{metric_val}</b>\n"
            f"CBS Score: <b>{cbs}</b>\n"
            f"Time: {ts}"
        )

    async def send_message(self, text: str) -> None:
        """Send a plain text message (for system notifications)."""
        if not self._enabled:
            return
        url = (
            f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        )
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
