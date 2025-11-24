from typing import Dict, Tuple

from strategies.base import StrategyBase
from utils.models import Signal, Tick


ENTRY_THRESHOLD = 0.05
EXIT_THRESHOLD = 0.02
COST_PER_UNIT = 0.031
PRICE_BUFFER = 0.01
QTY = {"GOLDBEES": 10000, "SILVERBEES": 5000}


class ArbitrageCrossExchangeStrategy(StrategyBase):
    """Cross-exchange arbitrage strategy that emits signals consumed by the engine."""

    def __init__(self, name: str, parameters: Dict) -> None:
        super().__init__(name, parameters)
        self.symbols = parameters.get("symbols", ["GOLDBEES", "SILVERBEES"])
        self.positions = {sym: 0 for sym in self.symbols}
        self.book: Dict[Tuple[str, str], Dict[str, float]] = {}

    def on_tick(self, tick: Tick):
        if not self.active or tick.symbol not in self.symbols or not tick.exchange:
            return []
        # Store best bid/ask per (symbol, exchange)
        bid = tick.bid if tick.bid is not None else tick.price
        ask = tick.ask if tick.ask is not None else tick.price
        self.book[(tick.symbol, tick.exchange.upper())] = {"bid": bid, "ask": ask}
        return self._evaluate(tick.symbol)

    def _evaluate(self, sym: str):
        nse = self.book.get((sym, "NSE"), {})
        bse = self.book.get((sym, "BSE"), {})
        ask_nse, bid_nse = nse.get("ask"), nse.get("bid")
        ask_bse, bid_bse = bse.get("ask"), bse.get("bid")
        if None in (ask_nse, bid_nse, ask_bse, bid_bse):
            return []
        edge_buy_nse_sell_bse = (bid_bse - ask_nse) - COST_PER_UNIT
        edge_buy_bse_sell_nse = (bid_nse - ask_bse) - COST_PER_UNIT
        spread = abs(bid_nse - bid_bse)
        signals = []
        qty = QTY.get(sym, 0)

        # Entry signals
        if self.positions[sym] == 0:
            if edge_buy_bse_sell_nse > ENTRY_THRESHOLD:
                signals.extend(
                    [
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=ask_bse - PRICE_BUFFER,
                            signal_type="entry",
                            metadata={"exchange": "BSE", "edge": edge_buy_bse_sell_nse},
                        ),
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="SELL",
                            quantity=qty,
                            price=bid_nse + PRICE_BUFFER,
                            signal_type="entry",
                            metadata={"exchange": "NSE", "edge": edge_buy_bse_sell_nse},
                        ),
                    ]
                )
                self.positions[sym] = qty
            elif edge_buy_nse_sell_bse > ENTRY_THRESHOLD:
                signals.extend(
                    [
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=ask_nse - PRICE_BUFFER,
                            signal_type="entry",
                            metadata={"exchange": "NSE", "edge": edge_buy_nse_sell_bse},
                        ),
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="SELL",
                            quantity=qty,
                            price=bid_bse + PRICE_BUFFER,
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
                signals.extend(
                    [
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="BUY",
                            quantity=qty,
                            price=cover_price + PRICE_BUFFER,
                            signal_type="exit",
                            metadata={"exchange": cover_exch, "spread": spread},
                        ),
                        Signal(
                            strategy=self.name,
                            symbol=sym,
                            side="SELL",
                            quantity=qty,
                            price=square_price - PRICE_BUFFER,
                            signal_type="exit",
                            metadata={"exchange": square_exch, "spread": spread},
                        ),
                    ]
                )
                self.positions[sym] = 0
        return signals

    def reset(self) -> None:
        self.positions = {sym: 0 for sym in self.symbols}
        self.book.clear()
