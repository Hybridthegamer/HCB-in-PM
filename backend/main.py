"""HCB-in-PM backend application entrypoint.

Starts:
1. Database connection pool
2. Redis connection
3. Event listener (background WebSocket task)
4. API poller (background REST polling task)
5. Anomaly detector scheduler (every 6 hours via APScheduler)
6. FastAPI app served via uvicorn
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import settings
from database.connection import AsyncSessionLocal, init_db
from database.models import Market, Trade, Wallet
from ingestion.api_poller import ApiPoller
from ingestion.event_listener import EventListener
from ingestion.normaliser import TradeRecord
from notifications.email_notifier import EmailNotifier
from notifications.telegram_notifier import TelegramNotifier
from processing.alert_generator import evaluate_alerts
from processing.anomaly_detector import run_anomaly_detection
from processing.feature_extractor import extract_features
from processing.scoring_engine import score_wallet

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    ),
)
log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Application state container
# ---------------------------------------------------------------------------
class AppState:
    redis: Optional[aioredis.Redis] = None
    event_listener: Optional[EventListener] = None
    api_poller: Optional[ApiPoller] = None
    email_notifier: Optional[EmailNotifier] = None
    telegram_notifier: Optional[TelegramNotifier] = None
    scheduler: Optional[AsyncIOScheduler] = None


app_state = AppState()


# ---------------------------------------------------------------------------
# Trade processing pipeline
# ---------------------------------------------------------------------------
async def process_trade_event(record: TradeRecord, state: AppState) -> None:
    """Persist a normalised trade, then recompute CBS and evaluate alerts."""
    async with AsyncSessionLocal() as session:
        try:
            # Upsert Wallet
            wallet = await session.get(Wallet, record.wallet_id)
            if wallet is None:
                wallet = Wallet(
                    wallet_id=record.wallet_id,
                    first_seen=record.tx_timestamp,
                    total_trades=0,
                    updated_at=datetime.now(tz=timezone.utc),
                )
                session.add(wallet)
                await session.flush()

            # Upsert Market (create minimal placeholder if not known yet)
            market = await session.get(Market, record.market_id)
            if market is None:
                market = Market(
                    market_id=record.market_id,
                    question=f"Market {record.market_id}",
                )
                session.add(market)
                await session.flush()

            # Upsert Trade (skip if already stored)
            existing_trade = await session.get(Trade, record.trade_id)
            if existing_trade is not None:
                await session.commit()
                return

            trade = Trade(
                trade_id=record.trade_id,
                wallet_id=record.wallet_id,
                market_id=record.market_id,
                outcome=record.outcome,
                amount_usd=record.amount_usd,
                shares=record.shares,
                price_at_entry=record.price_at_entry,
                tx_timestamp=record.tx_timestamp,
                resolved=False,
                won=None,
            )
            session.add(trade)

            # Update wallet counters
            wallet.total_trades = (wallet.total_trades or 0) + 1
            wallet.updated_at = datetime.now(tz=timezone.utc)

            await session.flush()

            # Compute CBS
            features = await extract_features(record.wallet_id, session)
            if features is not None:
                score = await score_wallet(
                    record.wallet_id,
                    session,
                    state.redis,
                    features,
                )

                # Evaluate alerts if we got a score
                if score is not None:
                    wallet_refreshed = await session.get(Wallet, record.wallet_id)
                    if wallet_refreshed and state.email_notifier and state.telegram_notifier:
                        await evaluate_alerts(
                            score=score,
                            wallet=wallet_refreshed,
                            session=session,
                            email_notifier=state.email_notifier,
                            telegram_notifier=state.telegram_notifier,
                        )

            await session.commit()

        except Exception as exc:
            await session.rollback()
            log.error("trade_processing_error", error=str(exc), trade_id=record.trade_id)


async def process_market_event(raw_market: Dict[str, Any]) -> None:
    """Upsert a market record from the Gamma API."""
    market_id = (
        raw_market.get("conditionId")
        or raw_market.get("id")
        or raw_market.get("market_id")
    )
    if not market_id:
        return

    async with AsyncSessionLocal() as session:
        try:
            market = await session.get(Market, str(market_id))
            if market is None:
                market = Market(market_id=str(market_id))
                session.add(market)

            question = (
                raw_market.get("question")
                or raw_market.get("title")
                or f"Market {market_id}"
            )
            market.question = question
            market.category = raw_market.get("category") or raw_market.get("tags", [None])[0]

            volume = raw_market.get("volume") or raw_market.get("volumeNum") or 0
            try:
                market.total_volume_usd = float(volume)
            except (TypeError, ValueError):
                pass

            # Parse timestamps
            for attr, key in [
                ("close_time", "endDate"),
                ("resolved_at", "resolutionTime"),
                ("created_at", "createdAt"),
            ]:
                val = raw_market.get(key)
                if val:
                    try:
                        from ingestion.normaliser import _parse_timestamp
                        setattr(market, attr, _parse_timestamp(val))
                    except Exception:
                        pass

            market.resolution = raw_market.get("resolution") or raw_market.get("outcome")

            await session.commit()
        except Exception as exc:
            await session.rollback()
            log.warning("market_upsert_error", error=str(exc))


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    log.info("hcb_startup")

    # Store state on app
    app.state.email_notifier = app_state.email_notifier
    app.state.telegram_notifier = app_state.telegram_notifier
    app.state.redis = app_state.redis
    app.state.api_poller = app_state.api_poller

    # 1. Database
    await init_db()
    log.info("database_ready")

    # 2. Redis
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    app_state.redis = redis_client
    app.state.redis = redis_client
    log.info("redis_ready")

    # 3. Notifiers
    email_notifier = EmailNotifier()
    telegram_notifier = TelegramNotifier()
    app_state.email_notifier = email_notifier
    app_state.telegram_notifier = telegram_notifier
    app.state.email_notifier = email_notifier
    app.state.telegram_notifier = telegram_notifier

    # 4. Event listener (WebSocket)
    async def on_ws_trade(record: TradeRecord) -> None:
        await process_trade_event(record, app_state)

    event_listener = EventListener(on_trade=on_ws_trade)
    app_state.event_listener = event_listener
    await event_listener.start()
    log.info("event_listener_started")

    # 5. API poller (REST)
    async def on_poll_trade(record: TradeRecord) -> None:
        await process_trade_event(record, app_state)

    async def on_poll_market(raw: Dict[str, Any]) -> None:
        await process_market_event(raw)

    api_poller = ApiPoller(on_trade=on_poll_trade, on_market=on_poll_market)
    app_state.api_poller = api_poller
    app.state.api_poller = api_poller
    await api_poller.start()
    log.info("api_poller_started")

    # 6. APScheduler for anomaly detection
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_anomaly_detection,
        "interval",
        hours=settings.ANOMALY_DETECT_INTERVAL_HOURS,
        id="anomaly_detection",
        replace_existing=True,
    )
    scheduler.start()
    app_state.scheduler = scheduler
    log.info("scheduler_started", interval_hours=settings.ANOMALY_DETECT_INTERVAL_HOURS)

    yield  # application runs here

    # Shutdown
    log.info("hcb_shutdown")
    if app_state.scheduler:
        app_state.scheduler.shutdown(wait=False)
    if app_state.event_listener:
        await app_state.event_listener.stop()
    if app_state.api_poller:
        await app_state.api_poller.stop()
    if app_state.redis:
        await app_state.redis.aclose()
    log.info("hcb_shutdown_complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="HCB-in-PM API",
    description="High-Confidence Bets in Prediction Markets – REST API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(tz=timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.ENVIRONMENT == "development"),
        log_level=settings.LOG_LEVEL.lower(),
    )
