"""Periodic REST API poller for Polymarket CLOB and Gamma APIs.

Polls for new trades every POLL_INTERVAL_TRADES seconds and for market
metadata every POLL_INTERVAL_MARKETS seconds.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx
import structlog

from config import settings
from ingestion.normaliser import TradeRecord, normalise_clob_trade

log = structlog.get_logger(__name__)

TradeCallback = Callable[[TradeRecord], Coroutine[Any, Any, None]]
MarketCallback = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class ApiPoller:
    """Polls Polymarket REST endpoints for trades and market metadata."""

    CLOB_BASE = settings.POLYMARKET_CLOB_URL
    GAMMA_BASE = settings.POLYMARKET_GAMMA_URL

    def __init__(
        self,
        on_trade: TradeCallback,
        on_market: MarketCallback,
    ) -> None:
        self._on_trade = on_trade
        self._on_market = on_market
        self._running = False
        self._tasks: List[asyncio.Task] = []  # type: ignore[type-arg]
        self._seen_trade_ids: set = set()
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        self._running = True
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/json"},
        )
        self._tasks = [
            asyncio.create_task(self._poll_trades_loop()),
            asyncio.create_task(self._poll_markets_loop()),
        ]
        log.info("api_poller_started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._client:
            await self._client.aclose()
        log.info("api_poller_stopped")

    # ------------------------------------------------------------------
    # Trade polling
    # ------------------------------------------------------------------

    async def _poll_trades_loop(self) -> None:
        while self._running:
            try:
                await self._fetch_recent_trades()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("api_poller_trades_error", error=str(exc))
            await asyncio.sleep(settings.POLL_INTERVAL_TRADES)

    async def _fetch_recent_trades(self) -> None:
        assert self._client is not None
        url = f"{self.CLOB_BASE}/trades"
        params: Dict[str, Any] = {
            "limit": 500,
        }
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("api_poller_trades_http_error", error=str(exc))
            return

        try:
            payload = resp.json()
        except Exception:
            return

        # CLOB returns {"data": [...]} or just [...]
        trades_raw: List[Dict[str, Any]] = (
            payload.get("data", payload)
            if isinstance(payload, dict)
            else payload
        )
        if not isinstance(trades_raw, list):
            return

        new_count = 0
        for raw in trades_raw:
            record = normalise_clob_trade(raw)
            if record is None:
                continue
            if record.trade_id in self._seen_trade_ids:
                continue
            self._seen_trade_ids.add(record.trade_id)
            # Prevent unbounded growth of seen set
            if len(self._seen_trade_ids) > 100_000:
                self._seen_trade_ids = set(
                    list(self._seen_trade_ids)[-50_000:]
                )
            try:
                await self._on_trade(record)
                new_count += 1
            except Exception as exc:
                log.warning("api_poller_trade_callback_error", error=str(exc))

        if new_count:
            log.info("api_poller_new_trades", count=new_count)

    # ------------------------------------------------------------------
    # Market metadata polling
    # ------------------------------------------------------------------

    async def _poll_markets_loop(self) -> None:
        # Fetch immediately on startup
        try:
            await self._fetch_markets()
        except Exception as exc:
            log.warning("api_poller_markets_initial_error", error=str(exc))

        while self._running:
            await asyncio.sleep(settings.POLL_INTERVAL_MARKETS)
            try:
                await self._fetch_markets()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("api_poller_markets_error", error=str(exc))

    async def _fetch_markets(self) -> None:
        assert self._client is not None
        # Gamma API returns richer metadata (categories, questions)
        url = f"{self.GAMMA_BASE}/markets"
        params: Dict[str, Any] = {
            "active": "true",
            "limit": 200,
        }
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("api_poller_markets_http_error", error=str(exc))
            return

        try:
            payload = resp.json()
        except Exception:
            return

        markets_raw: List[Dict[str, Any]] = (
            payload if isinstance(payload, list)
            else payload.get("data", [])
        )
        for raw_market in markets_raw:
            try:
                await self._on_market(raw_market)
            except Exception as exc:
                log.warning("api_poller_market_callback_error", error=str(exc))

    # ------------------------------------------------------------------
    # Backfill for a specific wallet
    # ------------------------------------------------------------------

    async def backfill_wallet(
        self,
        wallet_address: str,
        on_trade: Optional[TradeCallback] = None,
    ) -> int:
        """Fetch all available trades for a single wallet address."""
        callback = on_trade or self._on_trade
        assert self._client is not None
        url = f"{self.CLOB_BASE}/trades"
        params: Dict[str, Any] = {
            "maker_address": wallet_address,
            "limit": 500,
        }
        total = 0
        page = 0
        while True:
            params["offset"] = page * 500
            try:
                resp = await self._client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                log.warning("backfill_error", wallet=wallet_address, error=str(exc))
                break

            trades_raw: List[Dict[str, Any]] = (
                payload.get("data", payload)
                if isinstance(payload, dict)
                else payload
            )
            if not trades_raw:
                break

            for raw in trades_raw:
                record = normalise_clob_trade(raw)
                if record is None:
                    continue
                try:
                    await callback(record)
                    total += 1
                except Exception as exc:
                    log.warning("backfill_callback_error", error=str(exc))

            if len(trades_raw) < 500:
                break
            page += 1

        log.info("backfill_complete", wallet=wallet_address, trades=total)
        return total
