import logging
import time
from typing import List, Optional

from quant_trading_system.brokers.base import BrokerBase
from quant_trading_system.risk.risk_manager import RiskManager
from quant_trading_system.utils.models import Fill, Order, Signal

logger = logging.getLogger(__name__)


class ExecutionEngine:
    def __init__(self, broker: BrokerBase, risk_manager: RiskManager, place_orders: bool = True) -> None:
        self.broker = broker
        self.risk_manager = risk_manager
        self.place_orders = place_orders

    def route_signal(self, signal: Signal) -> Optional[str]:
        order = self._signal_to_order(signal)
        if not self.risk_manager.approve_order(order):
            return None
        broker_choice = self._smart_route(order)
        if not self.place_orders:
            pseudo_id = f"paper-{int(time.time_ns())}"
            logger.info("Paper mode: skipping live order; would route to %s for %s", broker_choice, order)
            return pseudo_id
        logger.info("Routing order to %s for %s", broker_choice, order)
        try:
            order_id = self.broker.place_order(order)
        except Exception:
            logger.exception("Failed to place order for signal %s", signal)
            return None
        return order_id

    def _signal_to_order(self, signal: Signal) -> Order:
        exchange = signal.metadata.get("exchange", "NSE")
        return Order(
            symbol=signal.symbol,
            side=signal.side.upper(),
            quantity=signal.quantity,
            exchange=exchange,
            order_type="MARKET" if signal.price is None else "LIMIT",
            price=signal.price,
            metadata={"strategy": signal.strategy, **signal.metadata},
        )

    def _smart_route(self, order: Order) -> str:
        # Placeholder for multi-broker smart order routing; currently defaults to active broker.
        return self.broker.name()

    def simulate_fill(self, order_id: str, order: Order, price: float) -> Fill:
        """Used by backtests or demo mode to emulate a fill."""
        fill = Fill(order_id=order_id, symbol=order.symbol, side=order.side, quantity=order.quantity, price=price)
        pnl_delta = (price - (order.price or price)) * order.quantity * (1 if order.side == "SELL" else -1)
        self.risk_manager.record_fill(pnl_delta, order)
        return fill

    def poll_orders(self) -> List[Fill]:
        # In a live system you would poll broker APIs or consume order updates.
        logger.debug("poll_orders called - implement broker-specific status checks here")
        return []
