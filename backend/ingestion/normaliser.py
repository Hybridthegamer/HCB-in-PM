"""Normalise raw trade data from Polymarket into canonical TradeRecord objects."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog

log = structlog.get_logger(__name__)


@dataclass
class TradeRecord:
    trade_id: str
    wallet_id: str          # maker or taker address (lowercase)
    market_id: str
    outcome: str            # "YES" or "NO"
    amount_usd: float
    shares: float
    price_at_entry: float   # in [0, 1]
    tx_timestamp: datetime  # UTC


class NormaliserError(ValueError):
    pass


def _parse_timestamp(raw: Any) -> datetime:
    """Accept unix seconds (int/float) or ISO string."""
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    if isinstance(raw, str):
        # Try ISO with or without trailing Z
        raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    raise NormaliserError(f"Cannot parse timestamp: {raw!r}")


def _derive_trade_id(raw: Dict[str, Any]) -> str:
    """Generate a stable trade ID from transaction hash + taker + market."""
    key = (
        str(raw.get("transaction_hash", ""))
        + str(raw.get("taker_order_id", ""))
        + str(raw.get("market", ""))
        + str(raw.get("timestamp", ""))
    )
    return "0x" + hashlib.sha256(key.encode()).hexdigest()[:64]


def normalise_clob_trade(raw: Dict[str, Any]) -> Optional[TradeRecord]:
    """
    Normalise a trade object returned by the Polymarket CLOB REST API or
    pushed via WebSocket.

    Returns None (and logs a warning) if required fields are missing.
    """
    try:
        # Wallet address: prefer taker_address (market order side), fall back to maker
        wallet_raw: Optional[str] = (
            raw.get("taker_address")
            or raw.get("maker_address")
            or raw.get("trader_address")
        )
        if not wallet_raw:
            log.warning("normaliser_missing_wallet", raw=raw)
            return None

        wallet_id = wallet_raw.lower().strip()
        if len(wallet_id) > 42:
            wallet_id = wallet_id[:42]

        market_id: Optional[str] = raw.get("market") or raw.get("condition_id") or raw.get("market_id")
        if not market_id:
            log.warning("normaliser_missing_market", raw=raw)
            return None
        market_id = str(market_id).strip()

        # Outcome token side
        outcome_raw = (
            raw.get("outcome")
            or raw.get("side")
            or raw.get("token_id")
            or "YES"
        )
        outcome = str(outcome_raw).upper()
        if outcome not in ("YES", "NO", "BUY", "SELL"):
            outcome = "YES"
        if outcome in ("BUY",):
            outcome = "YES"
        if outcome in ("SELL",):
            outcome = "NO"

        # Shares
        shares_raw = raw.get("size") or raw.get("shares") or raw.get("original_size") or 0
        shares = float(shares_raw)

        # Price at entry (should be between 0 and 1)
        price_raw = raw.get("price") or raw.get("avg_price") or raw.get("price_at_entry") or 0.5
        price = float(price_raw)
        if price > 1.0:
            # Some APIs return price as cents (0-100)
            price = price / 100.0
        price = max(0.0001, min(0.9999, price))

        # Amount USD = shares * price
        amount_raw = raw.get("amount") or raw.get("amount_usd") or raw.get("cost")
        if amount_raw is not None:
            amount_usd = float(amount_raw)
            if amount_usd > 1_000_000:
                # Likely in USDC micro-units (6 decimals)
                amount_usd = amount_usd / 1_000_000
        else:
            amount_usd = shares * price

        # Timestamp
        ts_raw = raw.get("timestamp") or raw.get("created_at") or raw.get("transaction_time")
        if ts_raw is None:
            log.warning("normaliser_missing_timestamp", raw=raw)
            return None
        tx_timestamp = _parse_timestamp(ts_raw)

        # Trade ID
        trade_id_raw = raw.get("id") or raw.get("trade_id") or raw.get("transaction_hash")
        if trade_id_raw:
            trade_id = str(trade_id_raw).strip()
            if not trade_id.startswith("0x"):
                trade_id = "0x" + trade_id
            trade_id = trade_id[:66]
        else:
            trade_id = _derive_trade_id(raw)

        return TradeRecord(
            trade_id=trade_id,
            wallet_id=wallet_id,
            market_id=market_id,
            outcome=outcome[:10],
            amount_usd=round(amount_usd, 4),
            shares=round(shares, 8),
            price_at_entry=round(price, 4),
            tx_timestamp=tx_timestamp,
        )

    except Exception as exc:
        log.warning("normaliser_error", error=str(exc), raw=raw)
        return None
