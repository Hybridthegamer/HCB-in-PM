"""SQLAlchemy ORM models matching the 6-table schema."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Wallet(Base):
    __tablename__ = "wallet"

    wallet_id: Mapped[str] = mapped_column(String(42), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    avg_position_usd: Mapped[Optional[float]] = mapped_column(Numeric(18, 4))
    composite_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    label: Mapped[Optional[str]] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trades: Mapped[List["Trade"]] = relationship(
        "Trade", back_populates="wallet", lazy="select"
    )
    behavioral_scores: Mapped[List["BehavioralScore"]] = relationship(
        "BehavioralScore", back_populates="wallet", lazy="select"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="wallet", lazy="select"
    )


class Market(Base):
    __tablename__ = "market"

    market_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    close_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    resolution: Mapped[Optional[str]] = mapped_column(String(50))
    total_volume_usd: Mapped[float] = mapped_column(
        Numeric(18, 4), default=0
    )

    trades: Mapped[List["Trade"]] = relationship(
        "Trade", back_populates="market", lazy="select"
    )


class Trade(Base):
    __tablename__ = "trade"

    trade_id: Mapped[str] = mapped_column(String(66), primary_key=True)
    wallet_id: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallet.wallet_id"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("market.market_id"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    shares: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    price_at_entry: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    tx_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    won: Mapped[Optional[bool]] = mapped_column(Boolean)

    wallet: Mapped["Wallet"] = relationship(
        "Wallet", back_populates="trades"
    )
    market: Mapped["Market"] = relationship(
        "Market", back_populates="trades"
    )


class BehavioralScore(Base):
    """TimescaleDB hypertable on computed_at."""

    __tablename__ = "behavioral_score"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallet.wallet_id"), nullable=False
    )
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    position_size_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    timing_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    consistency_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    composite_score: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wallet: Mapped["Wallet"] = relationship(
        "Wallet", back_populates="behavioral_scores"
    )


class AlertRule(Base):
    __tablename__ = "alert_rule"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="rule", lazy="select"
    )


class Alert(Base):
    __tablename__ = "alert"

    alert_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    wallet_id: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallet.wallet_id"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_rule.rule_id"), nullable=False
    )
    composite_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    triggered_metric: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    dispatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    channels_notified: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text)
    )

    wallet: Mapped["Wallet"] = relationship(
        "Wallet", back_populates="alerts"
    )
    rule: Mapped["AlertRule"] = relationship(
        "AlertRule", back_populates="alerts"
    )
