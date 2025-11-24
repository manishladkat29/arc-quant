from collections import deque
from statistics import mean, pstdev
from typing import Deque, Dict, List

from quant_trading_system.strategies.base import StrategyBase
from quant_trading_system.utils.models import Bar, Signal


class MeanReversionStrategy(StrategyBase):
    def __init__(self, name: str, parameters: Dict) -> None:
        super().__init__(name, parameters)
        self.lookback = int(parameters.get("lookback_window", 20))
        self.entry_threshold = float(parameters.get("entry_threshold", 2.5))
        self.exit_threshold = float(parameters.get("exit_threshold", 0.5))
        self.symbol = parameters.get("symbol", "")
        self.quantity = int(parameters.get("quantity", 1))
        self.window: Deque[float] = deque(maxlen=self.lookback)

    def on_bar(self, bar: Bar) -> List[Signal]:
        if not self.active or bar.symbol != self.symbol:
            return []
        self.window.append(bar.close)
        if len(self.window) < self.lookback:
            return []
        mu = mean(self.window)
        sigma = pstdev(self.window) or 1e-6
        z = (bar.close - mu) / sigma
        signals: List[Signal] = []
        if z > self.entry_threshold:
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=self.symbol,
                    side="SELL",
                    quantity=self.quantity,
                    price=None,
                    signal_type="entry",
                    metadata={"zscore": f"{z:.2f}", "rule": "above_upper_band"},
                )
            )
        elif z < -self.entry_threshold:
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=self.symbol,
                    side="BUY",
                    quantity=self.quantity,
                    price=None,
                    signal_type="entry",
                    metadata={"zscore": f"{z:.2f}", "rule": "below_lower_band"},
                )
            )
        elif abs(z) < self.exit_threshold:
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=self.symbol,
                    side="SELL" if z > 0 else "BUY",
                    quantity=self.quantity,
                    price=None,
                    signal_type="exit",
                    metadata={"zscore": f"{z:.2f}", "rule": "mean_reversion_exit"},
                )
            )
        return signals

    def reset(self) -> None:
        self.window.clear()
