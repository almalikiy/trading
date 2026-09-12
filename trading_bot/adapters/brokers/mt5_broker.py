from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_bot.adapters.brokers.base_adapter import BaseAdapter
from trading_bot.core.domain.enums import OrderSide, OrderType, PositionSide
from trading_bot.core.domain.models import AccountSummary, Candle, OrderExecution, OrderRequest, Position, SymbolQuote

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - runtime environment dependency
    mt5 = None


def _require_mt5_keep_alive_permission(terminal_path: str | None = None) -> None:
    try:
        from trading_bot.app import terminal_adapters as terminal_adapters
    except Exception:
        return
    if not terminal_adapters._is_keep_terminal_alive_enabled():
        raise RuntimeError("MT5 startup denied: Keep MT5 alive is disabled.")


class MT5BrokerAdapter(BaseAdapter):
    name = "mt5"

    _TIMEFRAME_MAP = {
        "M1": "TIMEFRAME_M1",
        "M5": "TIMEFRAME_M5",
        "M15": "TIMEFRAME_M15",
        "M30": "TIMEFRAME_M30",
        "H1": "TIMEFRAME_H1",
        "H4": "TIMEFRAME_H4",
        "D1": "TIMEFRAME_D1",
    }

    def __init__(
        self,
        terminal_path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ) -> None:
        self.terminal_path = terminal_path
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.last_error: str | None = None

    def _normalize_timeframe(self, timeframe: str) -> Any:
        if mt5 is None:
            return None
        key = timeframe.upper()
        attribute = self._TIMEFRAME_MAP.get(key)
        if not attribute:
            return getattr(mt5, f"TIMEFRAME_{key}", None)
        return getattr(mt5, attribute, None)

    async def connect(self) -> None:
        if mt5 is None:
            self.connected = False
            self.last_error = "MetaTrader5 package is not installed or not available in this environment."
            return

        _require_mt5_keep_alive_permission(self.terminal_path)
        initialized = mt5.initialize(path=self.terminal_path or "")
        if not initialized:
            self.connected = False
            self.last_error = mt5.last_error() or "MT5 initialization failed"
            return

        if self.login is not None and self.password is not None and self.server:
            logged_in = mt5.login(self.login, password=str(self.password), server=self.server)
            if not logged_in:
                self.connected = False
                self.last_error = mt5.last_error() or "MT5 login failed"
                return

        self.connected = True
        self.last_error = None

    async def disconnect(self) -> None:
        if mt5 is not None:
            mt5.shutdown()
        self.connected = False
        self.last_error = None

    async def health_check(self) -> bool:
        if mt5 is None:
            return False
        if not self.connected:
            return False
        try:
            info = mt5.terminal_info()
            return bool(info is not None)
        except Exception as exc:  # pragma: no cover - runtime environment dependency
            self.last_error = str(exc)
            return False

    async def get_account_summary(self) -> AccountSummary:
        if mt5 is None or not self.connected:
            return AccountSummary(
                broker=self.name,
                balance=Decimal("0.00"),
                equity=Decimal("0.00"),
                margin_used=Decimal("0.00"),
                free_margin=Decimal("0.00"),
                leverage=Decimal("1"),
                currency="USD",
            )

        account = mt5.account_info()
        if account is None:
            raise RuntimeError(self.last_error or "MT5 account info unavailable")

        return AccountSummary(
            broker=self.name,
            balance=Decimal(str(account.balance or 0.0)),
            equity=Decimal(str(account.equity or 0.0)),
            margin_used=Decimal(str(account.margin or 0.0)),
            free_margin=Decimal(str(account.margin_free or 0.0)),
            leverage=Decimal(str(account.leverage or 1)),
            currency=(account.currency or "USD"),
        )

    async def get_ticker(self, symbol: str) -> SymbolQuote:
        if mt5 is None or not self.connected:
            return SymbolQuote(
                symbol=symbol,
                bid=Decimal("0.00"),
                ask=Decimal("0.00"),
                last=Decimal("0.00"),
                timestamp=datetime.utcnow(),
                spread=Decimal("0.00"),
            )

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 tick unavailable for {symbol}")

        return SymbolQuote(
            symbol=symbol,
            bid=Decimal(str(tick.bid)),
            ask=Decimal(str(tick.ask)),
            last=Decimal(str(tick.last)),
            timestamp=datetime.fromtimestamp(tick.time),
            spread=Decimal(str(max(tick.ask - tick.bid, 0.0))),
        )

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if mt5 is None or not self.connected:
            return []

        timeframe_id = self._normalize_timeframe(timeframe)
        if timeframe_id is None:
            raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")

        rates = mt5.copy_rates_from_pos(symbol, timeframe_id, 0, limit)
        if rates is None:
            return []

        candles: list[Candle] = []
        for rate in rates:
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open=Decimal(str(rate[1])),
                    high=Decimal(str(rate[2])),
                    low=Decimal(str(rate[3])),
                    close=Decimal(str(rate[4])),
                    volume=Decimal(str(rate[5])),
                    timestamp=datetime.fromtimestamp(rate[0]),
                )
            )
        return candles

    async def get_positions(self) -> list[Position]:
        if mt5 is None or not self.connected:
            return []

        positions = mt5.positions_get()
        if positions is None:
            return []

        result: list[Position] = []
        for pos in positions:
            side = PositionSide.LONG if pos.type == mt5.POSITION_TYPE_BUY else PositionSide.SHORT
            result.append(
                Position(
                    broker=self.name,
                    symbol=pos.symbol,
                    side=side,
                    volume=Decimal(str(pos.volume)),
                    entry_price=Decimal(str(pos.price_open)),
                    mark_price=Decimal(str(pos.price_current)),
                    pnl=Decimal(str(pos.profit)),
                    open_time=datetime.fromtimestamp(pos.time),
                )
            )
        return result

    async def get_position(self, symbol: str) -> Position | None:
        if mt5 is None or not self.connected:
            return None
        position = mt5.positions_get(symbol=symbol)
        if not position:
            return None
        pos = position[0]
        side = PositionSide.LONG if pos.type == mt5.POSITION_TYPE_BUY else PositionSide.SHORT
        return Position(
            broker=self.name,
            symbol=pos.symbol,
            side=side,
            volume=Decimal(str(pos.volume)),
            entry_price=Decimal(str(pos.price_open)),
            mark_price=Decimal(str(pos.price_current)),
            pnl=Decimal(str(pos.profit)),
            open_time=datetime.fromtimestamp(pos.time),
        )

    async def place_order(self, request: OrderRequest) -> OrderExecution:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not self.connected:
            raise RuntimeError("MT5 is not connected")

        symbol = request.symbol
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"MT5 symbol {symbol} not available")

        if request.order_type == OrderType.MARKET:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"No tick available for {symbol}")
            price = tick.ask if request.side == OrderSide.BUY else tick.bid
        else:
            price = request.price if request.price is not None else Decimal(str(0))

        order_type = mt5.ORDER_TYPE_BUY if request.side == OrderSide.BUY else mt5.ORDER_TYPE_SELL
        if request.order_type == OrderType.LIMIT:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if request.side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_LIMIT
        elif request.order_type == OrderType.STOP:
            order_type = mt5.ORDER_TYPE_BUY_STOP if request.side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_STOP

        trade_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(request.volume),
            "type": int(order_type),
            "price": float(price),
            "sl": float(request.stop_loss) if request.stop_loss is not None else 0.0,
            "tp": float(request.take_profit) if request.take_profit is not None else 0.0,
            "deviation": 10,
            "magic": 0,
            "comment": request.client_order_id or "mt5-adapter",
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result = mt5.order_send(trade_request)
        success_codes = {mt5.TRADE_RETCODE_DONE}
        partial_code = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", None)
        if partial_code is not None:
            success_codes.add(partial_code)
        if result.retcode not in success_codes:
            raise RuntimeError(f"MT5 order rejected: {result.comment} (retcode={result.retcode})")

        return OrderExecution(
            broker=self.name,
            symbol=symbol,
            order_id=str(result.order),
            client_order_id=request.client_order_id,
            side=request.side,
            status="filled" if result.retcode == mt5.TRADE_RETCODE_DONE else "partial",
            filled_volume=Decimal(str(result.volume or request.volume)),
            average_price=Decimal(str(result.price or price)),
            raw_response={
                "retcode": result.retcode,
                "comment": result.comment,
                "request": trade_request,
            },
        )

    async def cancel_order(self, order_id: str) -> bool:
        if mt5 is None or not self.connected:
            return False
        result = mt5.order_cancel(int(order_id))
        return bool(result)

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        if mt5 is None or not self.connected:
            return {"order_id": order_id, "status": "not_connected"}
        orders = mt5.history_orders_get(0, 0)
        if orders is None:
            return {"order_id": order_id, "status": "unknown"}
        for item in orders:
            if str(item.order) == str(order_id):
                return {
                    "order_id": str(item.order),
                    "status": "filled" if item.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL) else "pending",
                    "symbol": item.symbol,
                    "comment": item.comment,
                }
        return {"order_id": order_id, "status": "not_found"}

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        if mt5 is None or not self.connected:
            return {"symbol": symbol, "status": "not_connected"}

        info = mt5.symbol_info(symbol)
        if info is None:
            return {"symbol": symbol, "status": "unavailable"}

        return {
            "symbol": symbol,
            "status": "available",
            "digits": int(info.digits),
            "min_lot": float(info.volume_min),
            "lot_step": float(info.volume_step),
            "swap_type": info.swap_mode,
            "spread": int(info.spread),
        }
