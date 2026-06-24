"""FastAPI route definitions for the HCB-in-PM REST API."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas import (
    AlertOut,
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
    BackfillRequest,
    BackfillResponse,
    MarketOut,
    PaginatedTrades,
    PaginatedWallets,
    ScoreHistoryPoint,
    SystemStats,
    TradeOut,
    WalletProfile,
    WalletSummary,
)
from database.connection import get_db
from database.models import Alert, AlertRule, BehavioralScore, Market, Trade, Wallet

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Wallets
# ---------------------------------------------------------------------------

@router.get("/wallets", response_model=PaginatedWallets)
async def list_wallets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    label: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Leaderboard of wallets sorted by composite_score DESC."""
    stmt = select(Wallet)
    if label:
        stmt = stmt.where(Wallet.label == label)
    if search:
        stmt = stmt.where(Wallet.wallet_id.ilike(f"%{search}%"))

    count_result = await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar_one()

    stmt = (
        stmt.order_by(Wallet.composite_score.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    wallets = result.scalars().all()

    return PaginatedWallets(
        total=total,
        page=page,
        page_size=page_size,
        items=[WalletSummary.model_validate(w) for w in wallets],
    )


@router.get("/wallets/{wallet_id}", response_model=WalletProfile)
async def get_wallet(
    wallet_id: str,
    trade_limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    wallet = await session.get(Wallet, wallet_id.lower())
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    trades_result = await session.execute(
        select(Trade)
        .where(Trade.wallet_id == wallet_id.lower())
        .order_by(Trade.tx_timestamp.desc())
        .limit(trade_limit)
    )
    trades = trades_result.scalars().all()

    profile = WalletProfile.model_validate(wallet)
    profile.trades = [TradeOut.model_validate(t) for t in trades]
    return profile


@router.get("/wallets/{wallet_id}/scores", response_model=List[ScoreHistoryPoint])
async def get_wallet_scores(
    wallet_id: str,
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
):
    """Return CBS time-series for a wallet."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(BehavioralScore)
        .where(
            BehavioralScore.wallet_id == wallet_id.lower(),
            BehavioralScore.computed_at >= cutoff,
        )
        .order_by(BehavioralScore.computed_at.asc())
    )
    scores = result.scalars().all()
    return [ScoreHistoryPoint.model_validate(s) for s in scores]


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

@router.get("/trades", response_model=PaginatedTrades)
async def list_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    wallet_id: Optional[str] = Query(None),
    market_id: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Trade)
    if wallet_id:
        stmt = stmt.where(Trade.wallet_id == wallet_id.lower())
    if market_id:
        stmt = stmt.where(Trade.market_id == market_id)
    if since:
        stmt = stmt.where(Trade.tx_timestamp >= since)
    if until:
        stmt = stmt.where(Trade.tx_timestamp <= until)

    count_result = await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar_one()

    stmt = (
        stmt.order_by(Trade.tx_timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    trades = result.scalars().all()

    return PaginatedTrades(
        total=total,
        page=page,
        page_size=page_size,
        items=[TradeOut.model_validate(t) for t in trades],
    )


# ---------------------------------------------------------------------------
# Markets
# ---------------------------------------------------------------------------

@router.get("/markets", response_model=List[MarketOut])
async def list_markets(
    limit: int = Query(100, ge=1, le=500),
    category: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Market)
    if category:
        stmt = stmt.where(Market.category == category)
    stmt = stmt.order_by(Market.total_volume_usd.desc().nullslast()).limit(limit)
    result = await session.execute(stmt)
    markets = result.scalars().all()
    return [MarketOut.model_validate(m) for m in markets]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=List[AlertOut])
async def list_alerts(
    limit: int = Query(100, ge=1, le=500),
    wallet_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Alert, AlertRule.rule_name)
        .join(AlertRule, Alert.rule_id == AlertRule.rule_id, isouter=True)
    )
    if wallet_id:
        stmt = stmt.where(Alert.wallet_id == wallet_id.lower())
    stmt = stmt.order_by(Alert.dispatched_at.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = result.all()

    out = []
    for alert, rule_name in rows:
        a = AlertOut.model_validate(alert)
        a.rule_name = rule_name
        out.append(a)
    return out


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------

@router.get("/alert-rules", response_model=List[AlertRuleOut])
async def list_alert_rules(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(AlertRule).order_by(AlertRule.rule_id)
    )
    return [AlertRuleOut.model_validate(r) for r in result.scalars().all()]


@router.post("/alert-rules", response_model=AlertRuleOut, status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    session: AsyncSession = Depends(get_db),
):
    rule = AlertRule(**body.model_dump())
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return AlertRuleOut.model_validate(rule)


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleOut)
async def update_alert_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    session: AsyncSession = Depends(get_db),
):
    rule = await session.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    await session.flush()
    await session.refresh(rule)
    return AlertRuleOut.model_validate(rule)


@router.delete("/alert-rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_db),
):
    rule = await session.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=SystemStats)
async def get_stats(session: AsyncSession = Depends(get_db)):
    today = datetime.now(tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    total_wallets = (
        await session.execute(select(func.count(Wallet.wallet_id)))
    ).scalar_one()
    total_trades = (
        await session.execute(select(func.count(Trade.trade_id)))
    ).scalar_one()
    total_markets = (
        await session.execute(select(func.count(Market.market_id)))
    ).scalar_one()
    alerts_today = (
        await session.execute(
            select(func.count(Alert.alert_id)).where(Alert.dispatched_at >= today)
        )
    ).scalar_one()
    anomaly_wallets = (
        await session.execute(
            select(func.count(Wallet.wallet_id)).where(
                Wallet.label == "anomaly-high"
            )
        )
    ).scalar_one()

    return SystemStats(
        total_wallets=total_wallets,
        total_trades=total_trades,
        total_markets=total_markets,
        alerts_today=alerts_today,
        anomaly_wallets=anomaly_wallets,
    )


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

@router.post("/backfill", response_model=BackfillResponse)
async def trigger_backfill(
    body: BackfillRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Trigger a historical trade backfill for a wallet address."""
    poller = getattr(request.app.state, "api_poller", None)
    if poller is None:
        raise HTTPException(
            status_code=503, detail="API poller not available"
        )

    # Import here to avoid circular imports
    from main import process_trade_event

    count = await poller.backfill_wallet(
        body.wallet_address.lower(),
        on_trade=lambda t: process_trade_event(t, request.app.state),
    )
    return BackfillResponse(
        wallet_address=body.wallet_address,
        trades_imported=count,
        message=f"Backfill complete: {count} trades imported.",
    )
