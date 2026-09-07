from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


__all__ = ["OrderSide", "OrderType", "PositionSide"]
