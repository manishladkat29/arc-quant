# Modular Quant Trading Infrastructure

Reference implementation inspired by the prompt for a broker-agnostic quant trading system with Zerodha Kite Connect as the first integration.

## Features
- Modular packages for data ingestion, strategies, execution, risk, portfolio, backtesting, scheduler, and config.
- Strategy plug-in interface with sample Trend-Following, Mean-Reversion, and Options Scalper implementations.
- Additional standalone strategy module for cross-exchange arbitrage on GOLDBEES/SILVERBEES (Zerodha) at `strategies/arbitrage_cross_exchange.py`.
- Broker abstraction with Zerodha client plus a DummyBroker for local/demo runs.
- Config-driven wiring via YAML with environment variable overrides for secrets.
- Basic logging with Slack/Telegram alert helpers.
- Backtest runner that replays OHLC CSV and simulates fills.
- Zerodha broker supports per-order exchange selection (NSE/BSE) for multi-venue strategies.

## Quickstart
```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run demo backfill using historical CSV bars
python main.py --mode backtest --historical path/to/bars.csv

# Run live (requires valid Kite credentials)
KITE_API_KEY=... KITE_API_SECRET=... KITE_ACCESS_TOKEN=... \
python main.py --mode live --config config/config.yaml

# Paper-trade with live data (real ticks, dummy orders)
KITE_API_KEY=... KITE_API_SECRET=... KITE_ACCESS_TOKEN=... \
python main.py --mode paper --config config/config.yaml
```

## Config
- Edit `config/config.yaml` to set broker credentials, strategy parameters, risk limits, schedule, and notification endpoints.
- Env var overrides: `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_ACCESS_TOKEN`, `SLACK_WEBHOOK`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Data
- Live: streams via Kite WebSocket; token mapping must be supplied in production.
- Backtest/demo: CSV with headers `symbol,open,high,low,close,volume,start,end` (ISO datetime).

## Deployment
- Build container: `docker build -t quant_trading_system .`
- Run container (demo mode by default): `docker run --rm quant_trading_system`
- For live, mount config and pass env secrets.
