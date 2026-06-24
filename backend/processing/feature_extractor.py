"""Extract wallet features needed to compute Composite Behavioral Score (CBS)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import structlog
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Trade, Market

log = structlog.get_logger(__name__)


@dataclass
class WalletFeatures:
    wallet_id: str
    resolved_count: int
    winning_count: int
    all_trade_count: int
    avg_usd: float
    p95_usd: float                          # P95 of all trades in DB last 30d
    per_category_win_rates: Dict[str, float] = field(default_factory=dict)
    winning_entry_prices: List[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.resolved_count < 10:
            return 0.0
        return self.winning_count / self.resolved_count


async def extract_features(
    wallet_id: str,
    session: AsyncSession,
) -> Optional[WalletFeatures]:
    """Load resolved trades for a wallet (last 90 days) and compute features."""
    cutoff_90 = datetime.now(tz=timezone.utc) - timedelta(days=90)
    cutoff_30 = datetime.now(tz=timezone.utc) - timedelta(days=30)

    # ------------------------------------------------------------------
    # 1. Fetch wallet's resolved trades in the last 90 days
    # ------------------------------------------------------------------
    stmt = (
        select(Trade, Market.category)
        .join(Market, Trade.market_id == Market.market_id, isouter=True)
        .where(
            Trade.wallet_id == wallet_id,
            Trade.resolved == True,  # noqa: E712
            Trade.tx_timestamp >= cutoff_90,
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        # Also check total trade count for wallets with no resolved trades yet
        count_stmt = select(func.count()).where(Trade.wallet_id == wallet_id)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar_one_or_none() or 0
        if total_count == 0:
            return None

    resolved_count = len(rows)
    winning_count = sum(1 for r in rows if r[0].won)
    amounts = [float(r[0].amount_usd) for r in rows]
    avg_usd = sum(amounts) / len(amounts) if amounts else 0.0

    # Winning entry prices for timing score
    winning_entry_prices = [
        float(r[0].price_at_entry) for r in rows if r[0].won
    ]

    # Per-category win rates
    category_wins: Dict[str, int] = {}
    category_resolved: Dict[str, int] = {}
    for trade, category in rows:
        cat = category or "unknown"
        category_resolved[cat] = category_resolved.get(cat, 0) + 1
        if trade.won:
            category_wins[cat] = category_wins.get(cat, 0) + 1

    per_category_win_rates: Dict[str, float] = {}
    for cat, total in category_resolved.items():
        wins = category_wins.get(cat, 0)
        per_category_win_rates[cat] = wins / total if total > 0 else 0.0

    # ------------------------------------------------------------------
    # 2. P95 of ALL trades in the last 30 days (system-wide)
    # ------------------------------------------------------------------
    p95_stmt = text(
        """
        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY amount_usd)
        FROM trade
        WHERE tx_timestamp >= :cutoff
        """
    )
    p95_result = await session.execute(p95_stmt, {"cutoff": cutoff_30})
    p95_row = p95_result.fetchone()
    p95_usd = float(p95_row[0]) if p95_row and p95_row[0] is not None else 1000.0

    # ------------------------------------------------------------------
    # 3. Total trade count (all time, not just resolved)
    # ------------------------------------------------------------------
    total_stmt = select(func.count()).where(Trade.wallet_id == wallet_id)
    total_result = await session.execute(total_stmt)
    all_trade_count = total_result.scalar_one_or_none() or 0

    return WalletFeatures(
        wallet_id=wallet_id,
        resolved_count=resolved_count,
        winning_count=winning_count,
        all_trade_count=all_trade_count,
        avg_usd=avg_usd,
        p95_usd=p95_usd,
        per_category_win_rates=per_category_win_rates,
        winning_entry_prices=winning_entry_prices,
    )
