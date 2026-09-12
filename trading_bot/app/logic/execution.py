from __future__ import annotations

from typing import Any

from trading_bot.app.db import get_mt5_error_log, log_mt5_error


def _require_mt5_keep_alive_permission(terminal_path: str | None = None) -> None:
    try:
        from trading_bot.app import terminal_adapters as terminal_adapters
    except Exception:
        return
    if not terminal_adapters._is_keep_terminal_alive_enabled():
        raise RuntimeError("MT5 startup denied: Keep MT5 alive is disabled.")

try:  # pragma: no cover - runtime dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


def order_result_payload(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if hasattr(result, "_asdict"):
        try:
            return dict(result._asdict())
        except Exception:
            return {"raw": str(result)}
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}


def send_order_with_fallback(request: dict[str, Any]) -> tuple[Any, int | None, str | None]:
    if mt5 is None:
        return None, None, "MetaTrader5 package is not installed"

    fill_modes = [getattr(mt5, "ORDER_FILLING_IOC", None)]
    for extra in ("ORDER_FILLING_FOK", "ORDER_FILLING_RETURN"):
        mode = getattr(mt5, extra, None)
        if mode is not None and mode not in fill_modes:
            fill_modes.append(mode)

    last_result = None
    last_retcode = None
    last_comment = None
    for fill_mode in fill_modes:
        request["type_filling"] = int(fill_mode)
        result = mt5.order_send(request)
        last_result = result
        last_retcode = getattr(result, "retcode", None)
        last_comment = getattr(result, "comment", None)
        done = getattr(mt5, "TRADE_RETCODE_DONE", None)
        partial = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", None)
        if last_retcode in {done, partial}:
            return result, last_retcode, last_comment
    return last_result, last_retcode, last_comment


def open_real_trade(symbol: str, lot: float, trade_type: str, terminal_path: str | None = None) -> dict[str, Any]:
    if mt5 is None:
        log_mt5_error("MT5 package unavailable (open_real_trade)")
        raise RuntimeError("MT5 not connected")

    initialized = False
    try:
        _require_mt5_keep_alive_permission(terminal_path)
        initialized = bool(mt5.initialize(path=terminal_path)) if terminal_path else bool(mt5.initialize())
        if not initialized:
            log_mt5_error("MT5 not connected (open_real_trade)")
            raise RuntimeError("MT5 not connected")

        side = str(trade_type or "").strip().lower()
        if side == "buy":
            order_type = mt5.ORDER_TYPE_BUY
        elif side == "sell":
            order_type = mt5.ORDER_TYPE_SELL
        else:
            raise ValueError("trade_type must be 'buy' or 'sell'")

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {symbol}")

        price = float(tick.ask) if side == "buy" else float(tick.bid)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": int(order_type),
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "",
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result, retcode, comment = send_order_with_fallback(request)
        done = getattr(mt5, "TRADE_RETCODE_DONE", None)
        partial = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", None)
        if retcode not in {done, partial}:
            message = f"Order send failed: {retcode} {comment}"
            log_mt5_error(message)
            raise RuntimeError(message)

        return {"status": "ok", "order": order_result_payload(result)}
    finally:
        if initialized:
            try:
                mt5.shutdown()
            except Exception:
                pass


def close_real_trade(symbol: str, lot: float, ticket: int, terminal_path: str | None = None) -> dict[str, Any]:
    if mt5 is None:
        log_mt5_error("MT5 package unavailable (close_real_trade)")
        raise RuntimeError("MT5 not connected")

    initialized = False
    try:
        _require_mt5_keep_alive_permission(terminal_path)
        initialized = bool(mt5.initialize(path=terminal_path)) if terminal_path else bool(mt5.initialize())
        if not initialized:
            log_mt5_error("MT5 not connected (close_real_trade)")
            raise RuntimeError("MT5 not connected")

        position = mt5.positions_get(ticket=ticket)
        if not position:
            message = f"No open position with ticket {ticket}"
            log_mt5_error(message)
            raise RuntimeError(message)

        pos = position[0]
        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = float(mt5.symbol_info_tick(symbol).bid)
        elif pos.type == mt5.POSITION_TYPE_SELL:
            order_type = mt5.ORDER_TYPE_BUY
            price = float(mt5.symbol_info_tick(symbol).ask)
        else:
            raise RuntimeError("Unknown position type")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": int(order_type),
            "position": int(ticket),
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "",
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result, retcode, comment = send_order_with_fallback(request)
        done = getattr(mt5, "TRADE_RETCODE_DONE", None)
        partial = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", None)
        if retcode not in {done, partial}:
            message = f"Order close failed: {retcode} {comment}"
            log_mt5_error(message)
            raise RuntimeError(message)

        return {"status": "ok", "order": order_result_payload(result)}
    finally:
        if initialized:
            try:
                mt5.shutdown()
            except Exception:
                pass


__all__ = [
    "open_real_trade",
    "close_real_trade",
    "send_order_with_fallback",
    "order_result_payload",
    "get_mt5_error_log",
]
