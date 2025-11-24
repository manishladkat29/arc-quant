import csv
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Deque, Dict, Iterable, List, Optional

try:
    from kiteconnect import KiteTicker  # type: ignore
except ImportError:
    KiteTicker = None  # pragma: no cover - optional dependency

from utils.models import Bar, Tick

logger = logging.getLogger(__name__)


class BarAggregator:
    """Aggregate ticks into OHLC bars for the given timeframe in seconds."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.buffers: Dict[str, List[Tick]] = defaultdict(list)
        self.current_window_start: Dict[str, datetime] = {}

    def update(self, tick: Tick) -> Optional[Bar]:
        start = self.current_window_start.get(tick.symbol)
        if start is None or tick.timestamp >= start + timedelta(seconds=self.interval_seconds):
            # Close previous bar if any.
            if start is not None and self.buffers[tick.symbol]:
                bar = self._build_bar(tick.symbol, start)
                self.buffers[tick.symbol].clear()
            else:
                bar = None
            self.current_window_start[tick.symbol] = self._get_window_start(tick.timestamp)
        else:
            bar = None
        self.buffers[tick.symbol].append(tick)
        return bar

    def _get_window_start(self, ts: datetime) -> datetime:
        seconds = int(ts.timestamp())
        bucket = seconds - (seconds % self.interval_seconds)
        return datetime.fromtimestamp(bucket)

    def _build_bar(self, symbol: str, start: datetime) -> Bar:
        ticks = self.buffers[symbol]
        prices = [t.price for t in ticks]
        volume = sum(t.volume for t in ticks)
        return Bar(
            symbol=symbol,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=volume,
            start=start,
            end=start + timedelta(seconds=self.interval_seconds),
        )


class DataFeed:
    """Unified interface for live WebSocket feed and historical data replay."""

    def __init__(
        self,
        symbols: Iterable[str],
        on_tick: Callable[[Tick], None],
        on_bar: Optional[Callable[[Bar], None]] = None,
        interval_seconds: int = 60,
        token_map: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> None:
        self.symbols = list(symbols)
        self.on_tick = on_tick
        self.on_bar = on_bar
        self.aggregator = BarAggregator(interval_seconds=interval_seconds)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._kite_ticker = None
        self.token_map = token_map or {}

    def start_live(self, api_key: str, access_token: str) -> None:
        if KiteTicker is None:
            raise ImportError("kiteconnect is required for live Zerodha streaming")
        logger.info("Starting live data feed for symbols: %s", self.symbols)
        self._kite_ticker = KiteTicker(api_key, access_token)

        self._kite_ticker.on_ticks = self._handle_kite_ticks
        self._kite_ticker.on_connect = self._on_connect
        self._kite_ticker.on_close = self._on_close

        self._thread = threading.Thread(target=self._kite_ticker.connect, kwargs={"threaded": True})
        self._thread.daemon = True
        self._thread.start()

    def start_historical_replay(self, csv_path: Path, speed: float = 1.0) -> None:
        """Replay historical ticks from a CSV with columns: symbol,price,volume,timestamp."""
        logger.info("Starting historical replay from %s", csv_path)
        self._stop.clear()
        self._thread = threading.Thread(target=self._replay_csv, args=(csv_path, speed), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        logger.info("Stopping data feed")
        self._stop.set()
        if self._kite_ticker:
            try:
                self._kite_ticker.close()
            except Exception:
                logger.exception("Failed to close Kite ticker cleanly")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _on_connect(self, ws, response) -> None:  # pragma: no cover - network callback
        logger.info("Connected to Zerodha WebSocket; subscribing tokens")
        # Placeholder: token mapping depends on instrument dump; use config mapping in production.
        self._kite_ticker.subscribe(self.symbols)
        self._kite_ticker.set_mode(self._kite_ticker.MODE_FULL, self.symbols)

    def _on_close(self, ws, code, reason) -> None:  # pragma: no cover - network callback
        logger.warning("Zerodha WebSocket closed (%s): %s", code, reason)

    def _handle_kite_ticks(self, ws, ticks) -> None:  # pragma: no cover - network callback
        for t in ticks:
            depth = t.get("depth", {})
            best_bids = depth.get("buy", [])
            best_asks = depth.get("sell", [])
            bid = best_bids[0]["price"] if best_bids else t.get("last_price", 0)
            ask = best_asks[0]["price"] if best_asks else t.get("last_price", 0)
            bid_size = best_bids[0].get("quantity") if best_bids else None
            ask_size = best_asks[0].get("quantity") if best_asks else None
            meta = self.token_map.get(t["instrument_token"], {})
            tick = Tick(
                symbol=meta.get("symbol", str(t["instrument_token"])),
                exchange=meta.get("exchange"),
                price=float(t.get("last_price", 0)),
                volume=float(t.get("volume", 0)),
                bid=bid,
                ask=ask,
                bid_size=bid_size,
                ask_size=ask_size,
                bid_depth=[{"price": b.get("price"), "quantity": b.get("quantity")} for b in best_bids],
                ask_depth=[{"price": a.get("price"), "quantity": a.get("quantity")} for a in best_asks],
                timestamp=datetime.utcnow(),
            )
            self._dispatch_tick(tick)

    def _dispatch_tick(self, tick: Tick) -> None:
        self.on_tick(tick)
        if self.on_bar:
            maybe_bar = self.aggregator.update(tick)
            if maybe_bar:
                self.on_bar(maybe_bar)

    def _replay_csv(self, csv_path: Path, speed: float) -> None:
        with csv_path.open("r") as fh:
            reader = csv.DictReader(fh)
            previous_ts: Optional[datetime] = None
            for row in reader:
                if self._stop.is_set():
                    break
                ts = datetime.fromisoformat(row["timestamp"])
                tick = Tick(
                    symbol=row["symbol"],
                    price=float(row["price"]),
                    volume=float(row["volume"]),
                    timestamp=ts,
                )
                if previous_ts:
                    delay = (ts - previous_ts).total_seconds() / speed
                    time.sleep(max(delay, 0))
                previous_ts = ts
                self._dispatch_tick(tick)
        self._stop.set()
