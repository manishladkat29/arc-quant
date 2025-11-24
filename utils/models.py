from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Tick:
    symbol: str
    price: float
    volume: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    bid_depth: List[Dict[str, float]] = field(default_factory=list)
    ask_depth: List[Dict[str, float]] = field(default_factory=list)
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None


@dataclass
class Bar:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    start: datetime
    end: datetime


@dataclass
class Signal:
    strategy: str
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    price: Optional[float] = None
    signal_type: str = "entry"
    metadata: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Order:
    symbol: str
    side: str
    quantity: int
    exchange: str = "NSE"
    order_type: str = "MARKET"
    price: Optional[float] = None
    time_in_force: str = "DAY"
    id: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Position:
    symbol: str
    quantity: int = 0
    average_price: float = 0.0

    def update(self, fill: Fill) -> None:
        if fill.side.upper() == "BUY":
            new_total_cost = self.average_price * self.quantity + fill.price * fill.quantity
            self.quantity += fill.quantity
            if self.quantity == 0:
                self.average_price = 0.0
            else:
                self.average_price = new_total_cost / self.quantity
        else:
            if self.quantity <= 0:
                # Increasing or initiating a short position
                new_total_cost = self.average_price * abs(self.quantity) + fill.price * fill.quantity
                self.quantity -= fill.quantity
                if self.quantity == 0:
                    self.average_price = 0.0
                else:
                    self.average_price = new_total_cost / abs(self.quantity)
            else:
                # Reducing a long; avg price unchanged unless we flip
                self.quantity -= fill.quantity
                if self.quantity == 0:
                    self.average_price = 0.0
                elif self.quantity < 0:
                    # Flipped to short; set entry reference to current fill price
                    self.average_price = fill.price


@dataclass
class RiskLimits:
    max_position_per_trade: int
    max_daily_drawdown: float
    max_total_leverage: float
    max_orders_per_minute: int = 60
