import abc
from typing import Dict, List

from utils.models import Bar, Signal, Tick


class StrategyBase(abc.ABC):
    def __init__(self, name: str, parameters: Dict) -> None:
        self.name = name
        self.parameters = parameters
        self.active = True

    def on_tick(self, tick: Tick) -> List[Signal]:
        return []

    def on_bar(self, bar: Bar) -> List[Signal]:
        return []

    def set_active(self, active: bool) -> None:
        self.active = active

    @abc.abstractmethod
    def reset(self) -> None:
        raise NotImplementedError
