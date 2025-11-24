import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from quant_trading_system.utils.models import Order, RiskLimits

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, limits: RiskLimits, starting_capital: float) -> None:
        self.limits = limits
        self.starting_capital = starting_capital
        self.realized_pnl = 0.0
        self.order_timestamps: Dict[str, Deque[float]] = defaultdict(deque)

    def approve_order(self, order: Order) -> bool:
        if order.quantity > self.limits.max_position_per_trade:
            logger.warning("Order %s exceeds position per trade limit", order)
            return False
        if not self._within_rate_limit(order.symbol):
            logger.warning("Order rate limit hit for %s", order.symbol)
            return False
        if self._breached_drawdown():
            logger.error("Trading halted due to drawdown limit reached")
            return False
        return True

    def record_fill(self, pnl_delta: float, order: Order) -> None:
        self.realized_pnl += pnl_delta
        self.order_timestamps[order.symbol].append(time.time())

    def _breached_drawdown(self) -> bool:
        return self.realized_pnl <= -self.starting_capital * self.limits.max_daily_drawdown

    def _within_rate_limit(self, symbol: str) -> bool:
        window = 60
        now = time.time()
        dq = self.order_timestamps[symbol]
        while dq and dq[0] < now - window:
            dq.popleft()
        return len(dq) < self.limits.max_orders_per_minute
