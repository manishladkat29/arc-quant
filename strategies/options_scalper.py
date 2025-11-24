from typing import Dict, List, Optional

from strategies.base import StrategyBase
from utils.models import Tick, Signal


class OptionsScalperStrategy(StrategyBase):
    """Lightweight placeholder for faster tick-driven options scalping."""

    def __init__(self, name: str, parameters: Dict) -> None:
        super().__init__(name, parameters)
        self.symbol = parameters.get("symbol", "")
        self.quantity = int(parameters.get("quantity", 1))
        self.spread_threshold = float(parameters.get("spread_threshold", 0.05))
        self.last_price: Optional[float] = None

    def on_tick(self, tick: Tick) -> List[Signal]:
        if not self.active or tick.symbol != self.symbol:
            return []
        signals: List[Signal] = []
        if self.last_price is not None:
            change = (tick.price - self.last_price) / self.last_price
            if abs(change) > self.spread_threshold:
                side = "BUY" if change > 0 else "SELL"
                signals.append(
                    Signal(
                        strategy=self.name,
                        symbol=self.symbol,
                        side=side,
                        quantity=self.quantity,
                        price=None,
                        signal_type="scalp",
                        metadata={"momentum": f"{change:.4f}"},
                    )
                )
        self.last_price = tick.price
        return signals

    def reset(self) -> None:
        self.last_price = None
