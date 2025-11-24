from datetime import datetime
from typing import List

from execution.execution_engine import ExecutionEngine
from risk.risk_manager import RiskManager
from strategies.arbitrage_cross_exchange import ArbitrageCrossExchangeStrategy
from utils.models import Order, RiskLimits, Signal, Tick
from portfolio.portfolio_manager import PortfolioManager


class LocalBroker:
    def __init__(self):
        self.orders = []

    def name(self):
        return "LocalBroker"

    def place_order(self, order: Order):
        self.orders.append(order)
        return f"order-{len(self.orders)}"

    def cancel_order(self, order_id: str):
        return True

    def get_positions(self):
        return []

    def get_balance(self):
        return {}


def run_sim():
    # Instantiate strategy
    strat = ArbitrageCrossExchangeStrategy(
        name="ArbTest",
        parameters={"symbols": ["GOLDBEES"]},
    )

    # Set up execution/risk/broker
    limits = RiskLimits(max_position_per_trade=20000, max_daily_drawdown=0.2, max_total_leverage=2.0, max_orders_per_minute=1000)
    risk = RiskManager(limits, starting_capital=1000000)
    broker = LocalBroker()
    engine = ExecutionEngine(broker=broker, risk_manager=risk, place_orders=True)
    portfolio = PortfolioManager()

    # Create synthetic ticks to trigger entry BUY BSE / SELL NSE
    ticks = [
        Tick(symbol="GOLDBEES", exchange="NSE", price=50.0, bid=50.0, ask=50.1, volume=1000, timestamp=datetime.utcnow()),
        Tick(symbol="GOLDBEES", exchange="BSE", price=50.2, bid=50.2, ask=50.3, volume=1000, timestamp=datetime.utcnow()),
    ]

    all_signals = []
    for t in ticks:
        sigs = strat.on_tick(t)
        all_signals.extend(sigs)
        for s in sigs:
            order_id = engine.route_signal(s)
            if order_id:
                fill_price = s.price or t.price
                fill = engine.simulate_fill(order_id, engine._signal_to_order(s), fill_price)
                portfolio.handle_fill(fill)

    return all_signals, broker.orders


def test_depth_caps_quantity():
    strat = ArbitrageCrossExchangeStrategy(
        name="ArbDepth",
        parameters={"symbols": ["GOLDBEES"], "depth_usage_pct": 0.5, "max_depth_levels": 2},
    )
    # Edge favors BUY BSE / SELL NSE; depth across first 2 levels allows 10k * 0.5 = 5k sizing.
    ticks = [
        Tick(
            symbol="GOLDBEES",
            exchange="NSE",
            price=50.5,
            bid=50.5,
            ask=50.6,
            bid_size=100,
            ask_size=200,
            bid_depth=[{"price": 50.5, "quantity": 100}, {"price": 50.49, "quantity": 9900}],
            ask_depth=[{"price": 50.6, "quantity": 200}],
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
        Tick(
            symbol="GOLDBEES",
            exchange="BSE",
            price=50.2,
            bid=50.2,
            ask=50.21,
            bid_size=100,
            ask_size=100,
            bid_depth=[{"price": 50.2, "quantity": 100}],
            ask_depth=[{"price": 50.2, "quantity": 100}, {"price": 50.21, "quantity": 9900}],
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
    ]

    signals: List[Signal] = []
    for t in ticks:
        signals.extend(strat.on_tick(t))

    assert len(signals) == 2
    assert {s.quantity for s in signals} == {5000}
    buy_sig = next(s for s in signals if s.side == "BUY")
    sell_sig = next(s for s in signals if s.side == "SELL")
    assert round(buy_sig.price, 2) == 50.22  # worst ask (50.21) + buffer (0.01)
    assert round(sell_sig.price, 2) == 50.48  # worst bid (50.49) - buffer (0.01)
    assert strat.positions["GOLDBEES"] == 5000


def test_exit_depth_caps_and_prices():
    strat = ArbitrageCrossExchangeStrategy(
        name="ArbExitDepth",
        parameters={"symbols": ["GOLDBEES"], "depth_usage_pct": 0.5, "max_depth_levels": 2},
    )
    strat.positions["GOLDBEES"] = 4000

    ticks = [
        Tick(
            symbol="GOLDBEES",
            exchange="NSE",
            price=50.0,
            bid=50.0,
            ask=50.01,
            bid_depth=[{"price": 50.0, "quantity": 1000}],
            ask_depth=[{"price": 50.01, "quantity": 600}, {"price": 50.02, "quantity": 1000}],
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
        Tick(
            symbol="GOLDBEES",
            exchange="BSE",
            price=49.99,
            bid=49.99,
            ask=50.0,
            bid_depth=[{"price": 49.99, "quantity": 1000}, {"price": 49.98, "quantity": 9000}],
            ask_depth=[{"price": 50.0, "quantity": 500}],
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
    ]

    signals: List[Signal] = []
    for t in ticks:
        signals.extend(strat.on_tick(t))

    assert len(signals) == 2
    assert {s.quantity for s in signals} == {800}  # min depth (1600) * 0.5
    cover_sig = next(s for s in signals if s.side == "BUY")
    square_sig = next(s for s in signals if s.side == "SELL")
    assert round(cover_sig.price, 2) == 50.03  # worst ask (50.02) + buffer
    assert round(square_sig.price, 2) == 49.97  # worst bid (49.98) - buffer
    assert strat.positions["GOLDBEES"] == 3200


def test_no_entry_when_edge_below_threshold():
    strat = ArbitrageCrossExchangeStrategy(
        name="ArbNoEntry",
        parameters={"symbols": ["GOLDBEES"]},
    )
    ticks = [
        Tick(symbol="GOLDBEES", exchange="NSE", price=50.0, bid=50.0, ask=50.01, volume=1000, timestamp=datetime.utcnow()),
        Tick(symbol="GOLDBEES", exchange="BSE", price=50.0, bid=50.0, ask=50.01, volume=1000, timestamp=datetime.utcnow()),
    ]
    signals: List[Signal] = []
    for t in ticks:
        signals.extend(strat.on_tick(t))
    assert signals == []
    assert strat.positions["GOLDBEES"] == 0


def test_entry_skips_when_depth_zero():
    strat = ArbitrageCrossExchangeStrategy(
        name="ArbZeroDepth",
        parameters={"symbols": ["GOLDBEES"], "depth_usage_pct": 0.8},
    )
    ticks = [
        Tick(
            symbol="GOLDBEES",
            exchange="NSE",
            price=50.0,
            bid=50.0,
            ask=50.05,
            bid_size=0,
            ask_size=0,
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
        Tick(
            symbol="GOLDBEES",
            exchange="BSE",
            price=50.1,
            bid=50.1,
            ask=50.15,
            bid_size=0,
            ask_size=0,
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
    ]
    signals: List[Signal] = []
    for t in ticks:
        signals.extend(strat.on_tick(t))
    assert signals == []
    assert strat.positions["GOLDBEES"] == 0


def test_exit_happens_over_multiple_ticks_when_depth_limited():
    strat = ArbitrageCrossExchangeStrategy(
        name="ArbExitMulti",
        parameters={"symbols": ["GOLDBEES"], "depth_usage_pct": 0.5, "max_depth_levels": 1},
    )
    strat.positions["GOLDBEES"] = 2000

    ticks = [
        Tick(
            symbol="GOLDBEES",
            exchange="NSE",
            price=50.0,
            bid=50.0,
            ask=50.01,
            ask_size=2000,
            bid_size=2000,
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
        Tick(
            symbol="GOLDBEES",
            exchange="BSE",
            price=50.0,
            bid=49.99,
            ask=50.0,
            ask_size=2000,
            bid_size=2000,
            volume=1000,
            timestamp=datetime.utcnow(),
        ),
    ]

    emitted: List[int] = []
    for _ in range(5):
        for t in ticks:
            sigs = strat.on_tick(t)
            emitted.extend(s.quantity for s in sigs)
        if strat.positions["GOLDBEES"] == 0:
            break

    # Each pass can exit min(2000,2000)*0.5=1000 per leg; two passes flatten 2000 position.
    assert strat.positions["GOLDBEES"] == 0
    assert sum(emitted) >= 4000  # total quantity across legs should cover both legs


if __name__ == "__main__":
    signals, orders = run_sim()
    assert len(signals) == 2, "Expected paired entry signals"
    assert set(o.exchange for o in orders) == {"NSE", "BSE"}, "Orders must target NSE and BSE"
    assert {"BUY", "SELL"} == set(o.side for o in orders), "Orders must be one BUY and one SELL"
    print("Signals emitted:", signals)
    print("Orders routed (exchange-aware):", [(o.symbol, o.side, o.exchange) for o in orders])
    print("Mock arbitrage test passed.")
