import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from quant_trading_system.execution.execution_engine import ExecutionEngine
from quant_trading_system.portfolio.portfolio_manager import PortfolioManager
from quant_trading_system.strategies.base import StrategyBase
from quant_trading_system.utils.models import Bar

logger = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(
        self,
        strategies: Iterable[StrategyBase],
        execution_engine: ExecutionEngine,
        portfolio: PortfolioManager,
    ) -> None:
        self.strategies: List[StrategyBase] = list(strategies)
        self.execution_engine = execution_engine
        self.portfolio = portfolio

    def run_from_csv(self, csv_path: Path) -> None:
        logger.info("Running backtest on %s", csv_path)
        with csv_path.open("r") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                bar = Bar(
                    symbol=row["symbol"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                    start=datetime.fromisoformat(row["start"]),
                    end=datetime.fromisoformat(row["end"]),
                )
                for strategy in self.strategies:
                    signals = strategy.on_bar(bar)
                    for sig in signals:
                        order_id = self.execution_engine.route_signal(sig)
                        if order_id:
                            fill = self.execution_engine.simulate_fill(order_id, self.execution_engine._signal_to_order(sig), bar.close)
                            self.portfolio.handle_fill(fill)
        logger.info("Backtest complete. Realized PnL: %.2f", self.portfolio.realized_pnl)
