"""Gaussian Mixture Model anomaly detection on CBS values.

Scheduled every ANOMALY_DETECT_INTERVAL_HOURS hours.
Wallets whose CBS > mean + 2*std of the highest-scoring GMM component
are labelled 'anomaly-high'.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

import numpy as np
import structlog
from sklearn.mixture import GaussianMixture
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import AsyncSessionLocal
from database.models import Wallet

log = structlog.get_logger(__name__)

# Minimum number of wallets needed to fit the GMM
MIN_WALLETS = 20


async def run_anomaly_detection() -> None:
    """Entry point called by APScheduler."""
    async with AsyncSessionLocal() as session:
        try:
            await _detect_anomalies(session)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            log.error("anomaly_detection_error", error=str(exc))


async def _detect_anomalies(session: AsyncSession) -> None:
    # Fetch wallets with >=10 trades that have a composite_score
    stmt = (
        select(Wallet.wallet_id, Wallet.composite_score)
        .where(
            Wallet.composite_score.isnot(None),
            Wallet.total_trades >= 10,
        )
    )
    result = await session.execute(stmt)
    rows: List[Tuple[str, float]] = [(r[0], float(r[1])) for r in result.all()]

    if len(rows) < MIN_WALLETS:
        log.info(
            "anomaly_detection_skipped",
            reason="insufficient_wallets",
            count=len(rows),
            required=MIN_WALLETS,
        )
        return

    wallet_ids = [r[0] for r in rows]
    cbs_values = np.array([r[1] for r in rows]).reshape(-1, 1)

    # Fit GMM with 3 components
    n_components = min(3, len(rows))
    gmm = GaussianMixture(
        n_components=n_components,
        covariance_type="full",
        random_state=42,
        max_iter=200,
    )
    gmm.fit(cbs_values)

    # Identify the component with the highest mean
    means = gmm.means_.flatten()
    best_component = int(np.argmax(means))
    best_mean = float(means[best_component])
    best_var = float(gmm.covariances_[best_component].flatten()[0])
    best_std = float(np.sqrt(best_var))
    threshold = best_mean + 2.0 * best_std

    log.info(
        "anomaly_gmm_fitted",
        n_wallets=len(rows),
        n_components=n_components,
        best_component=best_component,
        best_mean=round(best_mean, 4),
        best_std=round(best_std, 4),
        threshold=round(threshold, 4),
    )

    # Flag anomalous wallets
    anomaly_ids = [
        wid for wid, cbs in rows if cbs > threshold
    ]
    normal_ids = [
        wid for wid, cbs in rows if cbs <= threshold
    ]

    now = datetime.now(tz=timezone.utc)

    if anomaly_ids:
        await session.execute(
            update(Wallet)
            .where(Wallet.wallet_id.in_(anomaly_ids))
            .values(label="anomaly-high", updated_at=now)
        )

    # Reset labels for wallets that no longer qualify
    if normal_ids:
        await session.execute(
            update(Wallet)
            .where(
                Wallet.wallet_id.in_(normal_ids),
                Wallet.label == "anomaly-high",
            )
            .values(label=None, updated_at=now)
        )

    log.info(
        "anomaly_detection_complete",
        flagged=len(anomaly_ids),
        threshold=round(threshold, 4),
        anomaly_wallet_ids=anomaly_ids[:10],  # log first 10
    )
