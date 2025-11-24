import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional

import schedule

logger = logging.getLogger(__name__)


class TradingScheduler:
    def __init__(self, start_time: str, end_time: str, heartbeat_seconds: int, on_start: Callable, on_stop: Callable, on_heartbeat: Optional[Callable] = None) -> None:
        self.start_time = start_time
        self.end_time = end_time
        self.heartbeat_seconds = heartbeat_seconds
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_heartbeat = on_heartbeat
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        schedule.every().day.at(self.start_time).do(self._safe(self.on_start))
        schedule.every().day.at(self.end_time).do(self._safe(self.on_stop))
        if self.on_heartbeat and self.heartbeat_seconds:
            schedule.every(self.heartbeat_seconds).seconds.do(self._safe(self.on_heartbeat))
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Scheduler started with trading window %s-%s", self.start_time, self.end_time)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        schedule.clear()

    def _run(self) -> None:
        while not self._stop.is_set():
            schedule.run_pending()
            time.sleep(1)

    def _safe(self, func: Callable) -> Callable:
        def wrapper() -> None:
            try:
                func()
            except Exception:
                logger.exception("Scheduled task failed")
        return wrapper
