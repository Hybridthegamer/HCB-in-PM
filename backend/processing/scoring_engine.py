"""Compute Composite Behavioral Score (CBS) for a wallet.

CBS = 0.35*WR + 0.25*PS + 0.25*TS + 0.15*CS

All components are normalised to [0, 1].
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BehavioralScore, Wallet
from processing.feature_extractor import WalletFeatures

log = structlog.get_logger(__name__)


@dataclass
class ScoreResult:
    wallet_id: str
    win_rate: float
    position_size_score: float
    timing_score: float
    consistency_score: float
    composite_score: float


def compute_cbs(features: WalletFeatures) -> Optional[ScoreResult]:
    """Return CBS components or None if the wallet has <10 resolved trades."""
    if features.resolved_count < 10:
        log.debug(
            "scoring_insufficient_trades",
            wallet=features.wallet_id,
            resolved=features.resolved_count,
        )
        return None

    # ------------------------------------------------------------------
    # WR – Win Rate
    # ------------------------------------------------------------------
    wr = features.win_rate  # already 0 if resolved < 10

    # ------------------------------------------------------------------
    # PS – Position Size Score
    # min(1, avg_trade_size / P95_trade_size_30d)
    # ------------------------------------------------------------------
    if features.p95_usd > 0:
        ps = min(1.0, features.avg_usd / features.p95_usd)
    else:
        ps = 0.0

    # ------------------------------------------------------------------
    # TS – Timing Score
    # For each winning trade: TS_i = 1 - entry_price
    # (lower entry price => entered when odds were low => better timing)
    # wallet TS = mean(TS_i) over winning trades, naturally in [0,1]
    # ------------------------------------------------------------------
    if features.winning_entry_prices:
        ts_values = [1.0 - p for p in features.winning_entry_prices]
        ts = sum(ts_values) / len(ts_values)
    else:
        ts = 0.0
    ts = max(0.0, min(1.0, ts))

    # ------------------------------------------------------------------
    # CS – Consistency Score
    # CS = 1 - std(category_win_rates) / mean(category_win_rates)
    # Clamped to [0, 1]. CS = 1.0 if only 1 category.
    # ------------------------------------------------------------------
    cat_rates = list(features.per_category_win_rates.values())
    if len(cat_rates) <= 1:
        cs = 1.0
    else:
        mean_rate = sum(cat_rates) / len(cat_rates)
        if mean_rate == 0:
            cs = 0.0
        else:
            variance = sum((r - mean_rate) ** 2 for r in cat_rates) / len(cat_rates)
            std_rate = variance ** 0.5
            cs = 1.0 - (std_rate / mean_rate)
            cs = max(0.0, min(1.0, cs))

    # ------------------------------------------------------------------
    # CBS – Composite Behavioral Score
    # ------------------------------------------------------------------
    cbs = 0.35 * wr + 0.25 * ps + 0.25 * ts + 0.15 * cs
    cbs = max(0.0, min(1.0, round(cbs, 4)))

    return ScoreResult(
        wallet_id=features.wallet_id,
        win_rate=round(wr, 4),
        position_size_score=round(ps, 4),
        timing_score=round(ts, 4),
        consistency_score=round(cs, 4),
        composite_score=cbs,
    )


async def persist_score(
    result: ScoreResult,
    session: AsyncSession,
    redis_client,  # redis.asyncio client
) -> None:
    """Write score to behavioral_score hypertable, update wallet table, cache in Redis."""
    now = datetime.now(tz=timezone.utc)

    # Insert into behavioral_score
    score_row = BehavioralScore(
        wallet_id=result.wallet_id,
        win_rate=result.win_rate,
        position_size_score=result.position_size_score,
        timing_score=result.timing_score,
        consistency_score=result.consistency_score,
        composite_score=result.composite_score,
        computed_at=now,
    )
    session.add(score_row)

    # Update wallet summary columns
    wallet = await session.get(Wallet, result.wallet_id)
    if wallet:
        wallet.win_rate = result.win_rate
        wallet.composite_score = result.composite_score
        wallet.updated_at = now

    await session.flush()

    # Cache in Redis
    cache_key = f"wallet:score:{result.wallet_id}"
    cache_value = json.dumps(
        {
            "wallet_id": result.wallet_id,
            "win_rate": result.win_rate,
            "position_size_score": result.position_size_score,
            "timing_score": result.timing_score,
            "consistency_score": result.consistency_score,
            "composite_score": result.composite_score,
            "computed_at": now.isoformat(),
        }
    )
    try:
        await redis_client.setex(cache_key, 300, cache_value)  # TTL 300s
    except Exception as exc:
        log.warning("redis_cache_error", error=str(exc))

    log.info(
        "score_persisted",
        wallet=result.wallet_id,
        cbs=result.composite_score,
    )


async def score_wallet(
    wallet_id: str,
    session: AsyncSession,
    redis_client,
    features,
) -> Optional[ScoreResult]:
    """Top-level helper: compute + persist CBS for a wallet."""
    result = compute_cbs(features)
    if result is None:
        return None
    await persist_score(result, session, redis_client)
    return result
