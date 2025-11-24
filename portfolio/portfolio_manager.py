import logging
from typing import Dict

from quant_trading_system.utils.models import Fill, Position

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self) -> None:
        self.positions: Dict[str, Position] = {}
        self.realized_pnl = 0.0

    def handle_fill(self, fill: Fill) -> None:
        pos = self.positions.setdefault(fill.symbol, Position(symbol=fill.symbol))
        previous_qty = pos.quantity
        previous_avg = pos.average_price
        pos.update(fill)
        if fill.side.upper() == "SELL" and previous_qty > 0:
            pnl = (fill.price - previous_avg) * min(previous_qty, fill.quantity)
            self.realized_pnl += pnl
        elif fill.side.upper() == "BUY" and previous_qty < 0:
            pnl = (previous_avg - fill.price) * min(-previous_qty, fill.quantity)
            self.realized_pnl += pnl
        logger.info(
            "Position updated %s: qty=%s avg=%.2f realized_pnl=%.2f",
            fill.symbol,
            pos.quantity,
            pos.average_price,
            self.realized_pnl,
        )

    def close_all_positions(self) -> None:
        # In production, you would send market orders to flatten. This is a placeholder hook.
        logger.warning("close_all_positions invoked; implement broker calls to flatten exposure.")

    def snapshot(self) -> Dict[str, float]:
        return {sym: pos.quantity for sym, pos in self.positions.items()}
