"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Wallet schemas
# ---------------------------------------------------------------------------

class WalletSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wallet_id: str
    first_seen: datetime
    total_trades: int
    win_rate: Optional[float] = None
    avg_position_usd: Optional[float] = None
    composite_score: Optional[float] = None
    label: Optional[str] = None
    updated_at: datetime


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_id: str
    wallet_id: str
    market_id: str
    outcome: str
    amount_usd: float
    shares: float
    price_at_entry: float
    tx_timestamp: datetime
    resolved: bool
    won: Optional[bool] = None


class WalletProfile(WalletSummary):
    trades: List[TradeOut] = []


class ScoreHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    computed_at: datetime
    win_rate: Optional[float] = None
    position_size_score: Optional[float] = None
    timing_score: Optional[float] = None
    consistency_score: Optional[float] = None
    composite_score: float


# ---------------------------------------------------------------------------
# Market schemas
# ---------------------------------------------------------------------------

class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_id: str
    question: str
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    close_time: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    total_volume_usd: Optional[float] = None


# ---------------------------------------------------------------------------
# Alert schemas
# ---------------------------------------------------------------------------

class AlertRuleCreate(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=100)
    metric: str = Field(..., min_length=1, max_length=50)
    operator: str = Field(..., pattern=r"^(>|>=|<|<=|==|!=)$")
    threshold: float
    active: bool = True


class AlertRuleUpdate(BaseModel):
    rule_name: Optional[str] = Field(None, min_length=1, max_length=100)
    metric: Optional[str] = Field(None, min_length=1, max_length=50)
    operator: Optional[str] = Field(None, pattern=r"^(>|>=|<|<=|==|!=)$")
    threshold: Optional[float] = None
    active: Optional[bool] = None


class AlertRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: int
    rule_name: str
    metric: str
    operator: str
    threshold: float
    active: bool
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    wallet_id: str
    rule_id: int
    rule_name: Optional[str] = None
    composite_score: Optional[float] = None
    triggered_metric: Optional[float] = None
    dispatched_at: datetime
    channels_notified: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Paginated responses
# ---------------------------------------------------------------------------

class PaginatedWallets(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[WalletSummary]


class PaginatedTrades(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TradeOut]


# ---------------------------------------------------------------------------
# Stats + backfill
# ---------------------------------------------------------------------------

class SystemStats(BaseModel):
    total_wallets: int
    total_trades: int
    total_markets: int
    alerts_today: int
    anomaly_wallets: int


class BackfillRequest(BaseModel):
    wallet_address: str = Field(..., min_length=10, max_length=42)


class BackfillResponse(BaseModel):
    wallet_address: str
    trades_imported: int
    message: str
