# HCB-in-PM: High-Confidence Bets in Prediction Markets

An automated system that detects high-conviction traders ("high-confidence bets") on the Polymarket decentralized prediction market. It monitors wallet activity in real-time, computes Composite Behavioral Scores (CBS), detects anomalies using Gaussian Mixture Models, sends alerts via email/Telegram, and serves a React dashboard.

## Architecture

```
Polymarket CLOB API / WebSocket
         |
         v
  [Ingestion Layer]   event_listener.py + api_poller.py
                      (WebSocket + REST polling)
         |
         | normalised TradeRecord
         v
  [Processing Layer]  feature_extractor -> scoring_engine -> anomaly_detector
                      -> alert_generator
         |
    [PostgreSQL]  [Redis]
         |
         v
  [FastAPI REST]  -->  [React Dashboard]
```

## Tech Stack

- **Python 3.11** / FastAPI / SQLAlchemy 2.0 async
- **PostgreSQL 15** + TimescaleDB extension (hypertable for behavioral_score)
- **Redis 7** for caching CBS results
- **scikit-learn** Gaussian Mixture Model for anomaly detection
- **React 18** + Vite + Tailwind CSS + Recharts
- **Notifications**: SMTP email + Telegram Bot API
- **Deployment**: Docker Compose

## CBS Algorithm

```
WR  = winning_trades / resolved_trades  (0 if resolved_trades < 10)
PS  = min(1, avg_trade_size_usd / P95_trade_size_30d)
TS  = mean(1 - entry_price) for winning trades  (lower entry = better timing)
CS  = 1 - std(per_category_win_rates) / mean(per_category_win_rates)

CBS = 0.35*WR + 0.25*PS + 0.25*TS + 0.15*CS
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your credentials

# 2. Start all services
docker compose up -d

# 3. Access dashboard
open http://localhost:3000
# API docs
open http://localhost:8000/docs
```

## Environment Variables

See `.env.example` for all required variables.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/wallets | Leaderboard (paginated, sorted by CBS) |
| GET | /api/wallets/{id} | Wallet profile + trade history |
| GET | /api/wallets/{id}/scores | CBS time-series |
| GET | /api/trades | Recent trades (filterable) |
| GET | /api/markets | Market list |
| GET | /api/alerts | Alert log |
| GET | /api/alert-rules | List alert rules |
| POST | /api/alert-rules | Create alert rule |
| PUT | /api/alert-rules/{id} | Update alert rule |
| DELETE | /api/alert-rules/{id} | Delete alert rule |
| GET | /api/stats | System statistics |
| POST | /api/backfill | Trigger wallet backfill |

## Project Structure

```
backend/          Python FastAPI application
  config.py       Pydantic settings
  main.py         Application entrypoint
  database/       SQLAlchemy models + migrations
  ingestion/      WebSocket listener + REST poller
  processing/     Scoring, anomaly detection, alerts
  api/            FastAPI routes + schemas
  notifications/  Email + Telegram
frontend/         React 18 + Vite dashboard
scripts/          DB setup + supervisord config
```
