"""Real-time Polymarket WebSocket event listener.

Subscribes to the Polymarket CLOB WebSocket feed for live trade fills.
Uses tenacity for exponential-backoff reconnection.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

import structlog
import websockets
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_never,
    wait_exponential,
)

from config import settings
from ingestion.normaliser import TradeRecord, normalise_clob_trade

log = structlog.get_logger(__name__)

# Callback type: async function that receives a TradeRecord
TradeCallback = Callable[[TradeRecord], Coroutine[Any, Any, None]]


class EventListener:
    """Manages the WebSocket connection to Polymarket's trade feed."""

    WS_URL = settings.POLYMARKET_WS_URL

    def __init__(self, on_trade: TradeCallback) -> None:
        self._on_trade = on_trade
        self._running = False
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_forever())
        log.info("event_listener_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("event_listener_stopped")

    async def _run_forever(self) -> None:
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning(
                    "event_listener_connection_lost",
                    error=str(exc),
                )
                if self._running:
                    await asyncio.sleep(5)

    async def _connect_and_listen(self) -> None:
        log.info("event_listener_connecting", url=self.WS_URL)
        async with websockets.connect(  # type: ignore[attr-defined]
            self.WS_URL,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
        ) as ws:
            log.info("event_listener_connected")
            # Subscribe to all market trade events
            subscribe_msg = json.dumps(
                {
                    "auth": {},
                    "markets": [],          # empty = subscribe to all
                    "assets_ids": [],
                    "type": "Market",
                }
            )
            await ws.send(subscribe_msg)

            async for raw_msg in ws:
                if not self._running:
                    break
                await self._handle_message(raw_msg)

    async def _handle_message(self, raw_msg: str) -> None:
        try:
            data = json.loads(raw_msg)
        except json.JSONDecodeError:
            return

        # The WS may emit a list or a single dict
        events = data if isinstance(data, list) else [data]

        for event in events:
            event_type = event.get("event_type") or event.get("type") or ""
            # Trade fills come as 'trade', 'last_trade_price', or similar
            if event_type.lower() in ("trade", "fill", "order_fill", ""):
                await self._process_event(event)

    async def _process_event(self, event: Dict[str, Any]) -> None:
        record = normalise_clob_trade(event)
        if record is None:
            return
        try:
            await self._on_trade(record)
        except Exception as exc:
            log.warning("event_listener_callback_error", error=str(exc))
