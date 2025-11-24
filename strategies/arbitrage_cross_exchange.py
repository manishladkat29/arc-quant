from typing import Dict, Optional, Tuple

from strategies.base import StrategyBase
from utils.models import Signal, Tick


ENTRY_THRESHOLD = 0.05
EXIT_THRESHOLD = 0.02
DEFAULT_COST_PER_UNIT = 0.031
PRICE_BUFFER = 0.01
QTY = {"GOLDBEES": 10000, "SILVERBEES": 5000}
DEPTH_USAGE_PCT = 0.8
MAX_DEPTH_LEVELS = 3


class ArbitrageCrossExchangeStrategy(StrategyBase):
    """Cross-exchange arbitrage strategy that emits signals consumed by the engine."""

    def __init__(self, name: str, parameters: Dict) -> None:
        super().__init__(name, parameters)
        self.symbols = parameters.get("symbols", ["GOLDBEES", "SILVERBEES"])
        self.positions = {sym: 0 for sym in self.symbols}
        self.depth_usage_pct = parameters.get("depth_usage_pct", DEPTH_USAGE_PCT)
        self.max_depth_levels = parameters.get("max_depth_levels", MAX_DEPTH_LEVELS)
        self.cost_per_unit = parameters.get("cost_per_unit", DEFAULT_COST_PER_UNIT)
        self.cost_per_unit_by_symbol = parameters.get("cost_per_unit_by_symbol", {})
        self.book: Dict[Tuple[str, str], Dict[str, Optional[float]]] = {}

    def on_tick(self, tick: Tick):
        if not self.active or tick.symbol not in self.symbols or not tick.exchange:
            return []
        # Store best bid/ask per (symbol, exchange)
        bid = tick.bid if tick.bid is not None else tick.price
        ask = tick.ask if tick.ask is not None else tick.price
        self.book[(tick.symbol, tick.exchange.upper())] = {
            "bid": bid,
            "ask": ask,
            "bid_size": tick.bid_size,
            "ask_size": tick.ask_size,
            "bid_depth": tick.bid_depth,
            "ask_depth": tick.ask_depth,
        }
        return self._evaluate(tick.symbol)

    def _evaluate(self, sym: str):
        nse = self.book.get((sym, "NSE"), {})
        bse = self.book.get((sym, "BSE"), {})
        ask_nse, bid_nse = nse.get("ask"), nse.get("bid")
        ask_bse, bid_bse = bse.get("ask"), bse.get("bid")
        if None in (ask_nse, bid_nse, ask_bse, bid_bse):
            return []
        # Guard against bad quotes that create nonsensical edges (e.g., zero/negative or inverted books).
        if min(ask_nse, bid_nse, ask_bse, bid_bse) <= 0:
            return []
        fee = self.cost_per_unit_by_symbol.get(sym, self.cost_per_unit)
        edge_buy_nse_sell_bse = (bid_bse - ask_nse) - fee
        edge_buy_bse_sell_nse = (bid_nse - ask_bse) - fee
        spread = abs(bid_nse - bid_bse)
        signals = []
        base_qty = QTY.get(sym, 0)

        # Entry signals
        if self.positions[sym] == 0:
            if edge_buy_bse_sell_nse > ENTRY_THRESHOLD:
                buy_cap, buy_price = self._depth_capacity(
                    bse.get("ask_depth") or [], side="BUY", fallback_price=ask_bse
                )
                sell_cap, sell_price = self._depth_capacity(
                    nse.get("bid_depth") or [], side="SELL", fallback_price=bid_nse
                )
                qty = self._depth_capped_qty(
                    base_qty,
                    buy_size=buy_cap or bse.get("ask_size"),
                    sell_size=sell_cap or nse.get("bid_size"),
                )
                if qty <= 0:
                    return []
                buy_limit = self._depth_price("BUY", buy_price, ask_bse)
                sell_limit = self._depth_price("SELL", sell_price, bid_nse)
                signals.extend(
                    [
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=buy_limit,
                            signal_type="entry",
                            metadata={"exchange": "BSE", "edge": edge_buy_bse_sell_nse},
                        ),
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="SELL",
                            quantity=qty,
                            price=sell_limit,
                            signal_type="entry",
                            metadata={"exchange": "NSE", "edge": edge_buy_bse_sell_nse},
                        ),
                    ]
                )
                self.positions[sym] = qty
            elif edge_buy_nse_sell_bse > ENTRY_THRESHOLD:
                buy_cap, buy_price = self._depth_capacity(
                    nse.get("ask_depth") or [], side="BUY", fallback_price=ask_nse
                )
                sell_cap, sell_price = self._depth_capacity(
                    bse.get("bid_depth") or [], side="SELL", fallback_price=bid_bse
                )
                qty = self._depth_capped_qty(
                    base_qty,
                    buy_size=buy_cap or nse.get("ask_size"),
                    sell_size=sell_cap or bse.get("bid_size"),
                )
                if qty <= 0:
                    return []
                buy_limit = self._depth_price("BUY", buy_price, ask_nse)
                sell_limit = self._depth_price("SELL", sell_price, bid_bse)
                signals.extend(
                    [
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=buy_limit,
                            signal_type="entry",
                            metadata={"exchange": "NSE", "edge": edge_buy_nse_sell_bse},
                        ),
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="SELL",
                            quantity=qty,
                            price=sell_limit,
                            signal_type="entry",
                            metadata={"exchange": "BSE", "edge": edge_buy_nse_sell_bse},
                        ),
                    ]
                )
                self.positions[sym] = qty
        else:
            # Exit signals
            if spread <= EXIT_THRESHOLD:
                cover_exch = "NSE" if bid_nse > bid_bse else "BSE"
                square_exch = "BSE" if cover_exch == "NSE" else "NSE"
                cover_price = ask_nse if cover_exch == "NSE" else ask_bse
                square_price = bid_bse if square_exch == "BSE" else bid_nse
                cover_depth = nse.get("ask_depth") if cover_exch == "NSE" else bse.get("ask_depth")
                square_depth = bse.get("bid_depth") if square_exch == "BSE" else nse.get("bid_depth")
                cover_cap, cover_worst_price = self._depth_capacity(
                    cover_depth or [], side="BUY", fallback_price=cover_price
                )
                square_cap, square_worst_price = self._depth_capacity(
                    square_depth or [], side="SELL", fallback_price=square_price
                )
                cover_size = cover_cap or (nse.get("ask_size") if cover_exch == "NSE" else bse.get("ask_size"))
                square_size = square_cap or (bse.get("bid_size") if square_exch == "BSE" else nse.get("bid_size"))
                qty = self._depth_capped_qty(self.positions[sym], buy_size=cover_size, sell_size=square_size)
                if qty <= 0:
                    return []
                cover_limit = self._depth_price("BUY", cover_worst_price, cover_price)
                square_limit = self._depth_price("SELL", square_worst_price, square_price)
                signals.extend(
                    [
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=cover_limit,
                            signal_type="exit",
                            metadata={"exchange": cover_exch, "spread": spread},
                        ),
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="SELL",
                            quantity=qty,
                            price=square_limit,
                            signal_type="exit",
                            metadata={"exchange": square_exch, "spread": spread},
                        ),
                    ]
                )
                self.positions[sym] -= qty
        return signals

    def reset(self) -> None:
        self.positions = {sym: 0 for sym in self.symbols}
        self.book.clear()

    def _depth_capped_qty(self, desired_qty: int, buy_size: Optional[float] = None, sell_size: Optional[float] = None) -> int:
        """Limit order size to a fraction of top-of-book depth to reduce slippage."""
        if desired_qty <= 0:
            return 0
        sizes = [s for s in (buy_size, sell_size) if s is not None and s > 0]
        if not sizes:
            return desired_qty
        cap = int(min(sizes) * self.depth_usage_pct)
        if cap <= 0:
            return 0
        return min(desired_qty, cap)

    def _depth_capacity(
        self, depth: list, side: str, fallback_price: Optional[float] = None
    ) -> Tuple[int, Optional[float]]:
        """Return cumulative size and worst price across top N levels."""
        if not depth:
            return 0, fallback_price
        ordered = sorted(
            depth,
            key=lambda x: x.get("price", 0),
            reverse=(side.upper() == "SELL"),
        )
        total = 0
        worst_price: Optional[float] = None
        for level in ordered[: self.max_depth_levels]:
            qty = level.get("quantity")
            price = level.get("price")
            if qty is None or qty <= 0 or price is None:
                continue
            total += qty
            worst_price = price
        return total, worst_price or fallback_price

    def _depth_price(self, side: str, worst_price: Optional[float], fallback_price: float) -> float:
        """Set a limit price that is aggressive enough to reach the depth considered."""
        if worst_price is None:
            return fallback_price
        if side.upper() == "BUY":
            return worst_price + PRICE_BUFFER
        return worst_price - PRICE_BUFFER
