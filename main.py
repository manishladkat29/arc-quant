import argparse
import importlib
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List

from quant_trading_system.backtest.backtester import BacktestEngine
from quant_trading_system.brokers.base import BrokerBase
from quant_trading_system.brokers.zerodha import ZerodhaBroker
from quant_trading_system.config.settings import get_strategy_classes, load_config
from quant_trading_system.data.data_feed import DataFeed
from quant_trading_system.execution.execution_engine import ExecutionEngine
from quant_trading_system.portfolio.portfolio_manager import PortfolioManager
from quant_trading_system.risk.risk_manager import RiskManager
from quant_trading_system.scheduler.scheduler import TradingScheduler
from quant_trading_system.strategies.base import StrategyBase
from quant_trading_system.utils.models import RiskLimits, Signal, Tick, Bar
from quant_trading_system.utils.notifications import send_slack_alert, send_telegram_alert


class DummyBroker(BrokerBase):
    """Fallback broker that only logs actions; useful for dry runs."""

    def connect(self) -> None:
        logging.getLogger(__name__).info("DummyBroker connected (no-op)")

    def place_order(self, order):
        logging.getLogger(__name__).info("DummyBroker placing order: %s", order)
        return f"dummy-{time.time_ns()}"

    def cancel_order(self, order_id: str) -> bool:
        logging.getLogger(__name__).info("DummyBroker cancelled order: %s", order_id)
        return True

    def get_positions(self):
        return []

    def get_balance(self):
        return {}


def import_strategy(path: str, name: str, params: Dict) -> StrategyBase:
    module_name, class_name = path.rsplit(".", 1)
    if not module_name.startswith("quant_trading_system."):
        module_name = f"quant_trading_system.{module_name}"
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls(name=name, parameters=params)


def build_strategies(config: Dict) -> List[StrategyBase]:
    strategies = []
    for entry in config.get("strategies", []):
        if not entry.get("enabled", True):
            continue
        strategies.append(import_strategy(entry["class"], entry["name"], entry.get("parameters", {})))
    return strategies


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Modular Quant Trading Infrastructure")
    parser.add_argument("--config", help="Path to YAML config", default=None)
    parser.add_argument("--mode", choices=["live", "paper", "backtest", "demo"], default="demo")
    parser.add_argument("--historical", help="CSV path for backtest/demo data", default=None)
    args = parser.parse_args()

    setup_logging()
    config = load_config(args.config)
    notifications = config.get("notifications", {})
    broker_cfg = config.get("broker", {})
    risk_cfg = config.get("risk", {})

    limits = RiskLimits(
        max_position_per_trade=risk_cfg.get("max_position_per_trade", 0),
        max_daily_drawdown=risk_cfg.get("max_daily_drawdown", 0.0),
        max_total_leverage=risk_cfg.get("max_total_leverage", 1.0),
        max_orders_per_minute=risk_cfg.get("max_orders_per_minute", 60),
    )

    broker: BrokerBase
    if args.mode == "live":
        broker = ZerodhaBroker(
            api_key=broker_cfg["api_key"],
            api_secret=broker_cfg["api_secret"],
            access_token=broker_cfg["access_token"],
        )
    elif args.mode == "paper":
        broker = DummyBroker()
    else:
        broker = DummyBroker()
    broker.connect()

    risk_manager = RiskManager(limits, starting_capital=float(broker_cfg.get("capital", 0)))
    portfolio = PortfolioManager()
    strategies = build_strategies(config)
    execution_engine = ExecutionEngine(
        broker=broker,
        risk_manager=risk_manager,
        place_orders=args.mode == "live",
    )

    def handle_signals(signals: List[Signal]) -> None:
        for signal in signals:
            order_id = execution_engine.route_signal(signal)
            if order_id:
                # In live mode, fills are asynchronous; in demo/backtest, fill immediately.
                if args.mode != "live":
                    fill = execution_engine.simulate_fill(order_id, execution_engine._signal_to_order(signal), signal.price or 0)
                    portfolio.handle_fill(fill)

    def on_tick(tick: Tick) -> None:
        for strategy in strategies:
            signals = strategy.on_tick(tick)
            handle_signals(signals)

    def on_bar(bar: Bar) -> None:
        for strategy in strategies:
            signals = strategy.on_bar(bar)
            handle_signals(signals)

    def start_trading() -> None:
        for s in strategies:
            s.set_active(True)
            s.reset()
        notify("Trading window started")

    def stop_trading() -> None:
        for s in strategies:
            s.set_active(False)
        notify("Trading window ended")

    def heartbeat() -> None:
        notify(f"Heartbeat | PnL={portfolio.realized_pnl:.2f} | Positions={portfolio.snapshot()}")

    def notify(message: str) -> None:
        logging.getLogger(__name__).info(message)
        send_slack_alert(notifications.get("slack_webhook"), message)
        send_telegram_alert(notifications.get("telegram_bot_token"), notifications.get("telegram_chat_id"), message)

    scheduler_cfg = config.get("schedule", {}).get("trading_hours", {})
    scheduler = TradingScheduler(
        start_time=scheduler_cfg.get("start", "09:15"),
        end_time=scheduler_cfg.get("end", "15:30"),
        heartbeat_seconds=config.get("schedule", {}).get("run_heartbeat_every", 0),
        on_start=start_trading,
        on_stop=stop_trading,
        on_heartbeat=heartbeat,
    )

    if args.mode == "backtest":
        if not args.historical:
            raise ValueError("Backtest mode requires --historical pointing to CSV bars file")
        backtester = BacktestEngine(strategies, execution_engine, portfolio)
        backtester.run_from_csv(Path(args.historical))
        return

    symbols = [p.get("parameters", {}).get("symbol") for p in config.get("strategies", []) if p.get("parameters", {}).get("symbol")]
    token_map = {}
    if "token_map" in config.get("broker", {}):
        # token_map: {token: {symbol: "GOLDBEES", exchange: "NSE"}}
        token_map = {int(k): v for k, v in config["broker"]["token_map"].items()}

    if args.mode == "demo" and args.historical:
        data_feed = DataFeed(symbols=symbols, on_tick=on_tick, on_bar=on_bar, interval_seconds=60)
        data_feed.start_historical_replay(Path(args.historical))
    elif args.mode in ("live", "paper"):
        data_feed = DataFeed(symbols=symbols, on_tick=on_tick, on_bar=on_bar, interval_seconds=60, token_map=token_map)
        data_feed.start_live(api_key=broker_cfg["api_key"], access_token=broker_cfg["access_token"])
    else:
        data_feed = None

    scheduler.start()

    def shutdown(signum, frame):
        logging.getLogger(__name__).info("Received signal %s, shutting down", signum)
        scheduler.stop()
        if data_feed:
            data_feed.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)
        if args.mode != "live" and data_feed and data_feed._thread and not data_feed._thread.is_alive():
            logging.getLogger(__name__).info("Data replay finished; shutting down.")
            shutdown(signal.SIGTERM, None)


if __name__ == "__main__":
    main()
