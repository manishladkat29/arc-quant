from collections import deque
from typing import Deque, Dict, List

from strategies.base import StrategyBase
from utils.models import Bar, Signal


class TrendFollowStrategy(StrategyBase):
    def __init__(self, name: str, parameters: Dict) -> None:
        super().__init__(name, parameters)
        self.lookback = int(parameters.get("ma_length", 50))
        self.symbol = parameters.get("symbol", "")
        self.quantity = int(parameters.get("quantity", 1))
        self.take_profit = float(parameters.get("take_profit", 0.02))
        self.stop_loss = float(parameters.get("stop_loss", 0.01))
        self.window: Deque[float] = deque(maxlen=self.lookback)

    def on_bar(self, bar: Bar) -> List[Signal]:
        if not self.active or bar.symbol != self.symbol:
            return []
        self.window.append(bar.close)
        if len(self.window) < self.lookback:
            return []
        avg_price = sum(self.window) / len(self.window)
        signals: List[Signal] = []
        if bar.close > avg_price:
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=self.symbol,
                    side="BUY",
                    quantity=self.quantity,
                    price=None,
                    signal_type="entry",
                    metadata={"ma": str(avg_price), "rule": "price_above_ma"},
                )
            )
        elif bar.close < avg_price:
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=self.symbol,
                    side="SELL",
                    quantity=self.quantity,
                    price=None,
                    signal_type="entry",
                    metadata={"ma": str(avg_price), "rule": "price_below_ma"},
                )
            )
        return signals

    def reset(self) -> None:
        self.window.clear()
