import logging
from typing import Any, Dict, List

try:
    from kiteconnect import KiteConnect  # type: ignore
except ImportError:
    KiteConnect = None  # pragma: no cover - optional dependency

from brokers.base import BrokerBase
from utils.models import Order

logger = logging.getLogger(__name__)


class ZerodhaBroker(BrokerBase):
    def __init__(self, api_key: str, api_secret: str, access_token: str) -> None:
        if KiteConnect is None:
            raise ImportError("kiteconnect is required for ZerodhaBroker")
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.kite: KiteConnect = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)

    def connect(self) -> None:
        logger.info("Zerodha broker authenticated")

    def place_order(self, order: Order) -> str:
        logger.info("Placing order via Zerodha: %s", order)
        exchange = self.kite.EXCHANGE_NSE if order.exchange.upper() == "NSE" else self.kite.EXCHANGE_BSE
        response = self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR,
            exchange=exchange,
            tradingsymbol=order.symbol,
            transaction_type=order.side.upper(),
            quantity=order.quantity,
            order_type=self.kite.ORDER_TYPE_MARKET if order.order_type == "MARKET" else self.kite.ORDER_TYPE_LIMIT,
            price=order.price or 0,
            product=self.kite.PRODUCT_MIS,
            validity=order.time_in_force,
        )
        order.id = response["order_id"]
        return order.id

    def cancel_order(self, order_id: str) -> bool:
        logger.info("Cancelling order %s", order_id)
        self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR, order_id=order_id)
        return True

    def get_positions(self) -> List[Dict[str, Any]]:
        positions = self.kite.positions()
        return positions.get("net", [])

    def get_balance(self) -> Dict[str, Any]:
        return self.kite.margins()
