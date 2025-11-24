import abc
from typing import Any, Dict, List, Optional

from quant_trading_system.utils.models import Order


class BrokerBase(abc.ABC):
    @abc.abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def place_order(self, order: Order) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        raise NotImplementedError

    def name(self) -> str:
        return self.__class__.__name__
