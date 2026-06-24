"""Evaluate alert rules and dispatch notifications.

Rate limited to 1 alert per wallet per rule per ALERT_RATE_LIMIT_MINUTES.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Alert, AlertRule, Wallet
from processing.scoring_engine import ScoreResult

log = structlog.get_logger(__name__)

_OPERATORS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

_METRIC_MAP = {
    "composite_score": "composite_score",
    "win_rate": "win_rate",
    "position_size_score": "position_size_score",
    "timing_score": "timing_score",
    "consistency_score": "consistency_score",
    "avg_position_usd": "avg_position_usd",
    "total_trades": "total_trades",
}


async def evaluate_alerts(
    score: ScoreResult,
    wallet: Wallet,
    session: AsyncSession,
    email_notifier,
    telegram_notifier,
) -> None:
    """Evaluate all active alert rules against the freshly computed score."""
    # Fetch active rules
    rules_result = await session.execute(
        select(AlertRule).where(AlertRule.active == True)  # noqa: E712
    )
    rules: List[AlertRule] = list(rules_result.scalars().all())

    for rule in rules:
        metric_value = _get_metric_value(score, wallet, rule.metric)
        if metric_value is None:
            continue

        op = _OPERATORS.get(rule.operator)
        if op is None:
            log.warning("alert_unknown_operator", operator=rule.operator)
            continue

        if not op(metric_value, float(rule.threshold)):
            continue

        # Rate limit check
        if await _is_rate_limited(wallet.wallet_id, rule.rule_id, session):
            log.debug(
                "alert_rate_limited",
                wallet=wallet.wallet_id,
                rule=rule.rule_id,
            )
            continue

        # Create alert record
        alert = Alert(
            wallet_id=wallet.wallet_id,
            rule_id=rule.rule_id,
            composite_score=score.composite_score,
            triggered_metric=float(metric_value),
            dispatched_at=datetime.now(tz=timezone.utc),
            channels_notified=[],
        )
        session.add(alert)
        await session.flush()  # get alert_id

        channels: List[str] = []

        # Dispatch email
        try:
            await email_notifier.send_alert(alert, rule, wallet)
            channels.append("email")
        except Exception as exc:
            log.warning("alert_email_failed", error=str(exc))

        # Dispatch Telegram
        try:
            await telegram_notifier.send_alert(alert, rule, wallet)
            channels.append("telegram")
        except Exception as exc:
            log.warning("alert_telegram_failed", error=str(exc))

        alert.channels_notified = channels
        log.info(
            "alert_dispatched",
            wallet=wallet.wallet_id,
            rule=rule.rule_name,
            metric=rule.metric,
            value=metric_value,
            threshold=float(rule.threshold),
            channels=channels,
        )


def _get_metric_value(
    score: ScoreResult,
    wallet: Wallet,
    metric: str,
) -> Optional[float]:
    mapping = {
        "composite_score": score.composite_score,
        "win_rate": score.win_rate,
        "position_size_score": score.position_size_score,
        "timing_score": score.timing_score,
        "consistency_score": score.consistency_score,
        "avg_position_usd": float(wallet.avg_position_usd or 0),
        "total_trades": float(wallet.total_trades or 0),
    }
    return mapping.get(metric)


async def _is_rate_limited(
    wallet_id: str,
    rule_id: int,
    session: AsyncSession,
) -> bool:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(
        minutes=settings.ALERT_RATE_LIMIT_MINUTES
    )
    result = await session.execute(
        select(func.count(Alert.alert_id)).where(
            Alert.wallet_id == wallet_id,
            Alert.rule_id == rule_id,
            Alert.dispatched_at >= cutoff,
        )
    )
    count = result.scalar_one()
    return count > 0
