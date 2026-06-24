"""SMTP email notifications for HCB alerts."""
from __future__ import annotations

from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import aiosmtplib
import structlog

from config import settings

log = structlog.get_logger(__name__)


class EmailNotifier:
    """Sends alert emails via SMTP (aiosmtplib)."""

    def __init__(self) -> None:
        self._enabled = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
        if not self._enabled:
            log.warning("email_notifier_disabled", reason="SMTP credentials not configured")

    async def send_alert(self, alert, rule, wallet) -> None:
        if not self._enabled:
            return

        recipients = settings.alert_to_emails_list
        if not recipients:
            log.warning("email_notifier_no_recipients")
            return

        subject = (
            f"[HCB Monitor] Alert: {rule.rule_name} triggered for {wallet.wallet_id[:10]}..."
        )
        body = self._build_body(alert, rule, wallet)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.ALERT_FROM_EMAIL
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "html"))

        try:
            async with aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                use_tls=False,
                start_tls=True,
            ) as smtp:
                await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                await smtp.send_message(msg)
            log.info("email_sent", to=recipients, rule=rule.rule_name)
        except Exception as exc:
            log.error("email_send_failed", error=str(exc))
            raise

    def _build_body(self, alert, rule, wallet) -> str:
        ts = alert.dispatched_at.strftime("%Y-%m-%d %H:%M UTC")
        cbs = f"{alert.composite_score:.4f}" if alert.composite_score is not None else "N/A"
        metric_val = (
            f"{alert.triggered_metric:.4f}"
            if alert.triggered_metric is not None
            else "N/A"
        )
        return f"""
        <html><body style="font-family: sans-serif; color: #333;">
        <h2 style="color: #e63946;">HCB Monitor Alert</h2>
        <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Rule</b></td>
              <td style="padding: 8px; border: 1px solid #ddd;">{rule.rule_name}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Wallet</b></td>
              <td style="padding: 8px; border: 1px solid #ddd;"><code>{wallet.wallet_id}</code></td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Metric</b></td>
              <td style="padding: 8px; border: 1px solid #ddd;">{rule.metric} {rule.operator} {rule.threshold}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Triggered Value</b></td>
              <td style="padding: 8px; border: 1px solid #ddd;">{metric_val}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>CBS Score</b></td>
              <td style="padding: 8px; border: 1px solid #ddd;">{cbs}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Time</b></td>
              <td style="padding: 8px; border: 1px solid #ddd;">{ts}</td></tr>
        </table>
        <p style="color: #888; font-size: 12px; margin-top: 20px;">
          HCB-in-PM Automated Monitor
        </p>
        </body></html>
        """
