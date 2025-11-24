from datetime import datetime

from quant_trading_system.execution.execution_engine import ExecutionEngine
from quant_trading_system.risk.risk_manager import RiskManager
from quant_trading_system.strategies.arbitrage_cross_exchange import ArbitrageCrossExchangeStrategy
from quant_trading_system.utils.models import Order, RiskLimits, Signal, Tick
from quant_trading_system.portfolio.portfolio_manager import PortfolioManager


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


if __name__ == "__main__":
    signals, orders = run_sim()
    assert len(signals) == 2, "Expected paired entry signals"
    assert set(o.exchange for o in orders) == {"NSE", "BSE"}, "Orders must target NSE and BSE"
    assert {"BUY", "SELL"} == set(o.side for o in orders), "Orders must be one BUY and one SELL"
    print("Signals emitted:", signals)
    print("Orders routed (exchange-aware):", [(o.symbol, o.side, o.exchange) for o in orders])
    print("Mock arbitrage test passed.")
