from __future__ import annotations

from typing import Any, Callable

from trading_bot.app import db as _db

DB_PATH = _db.DB_PATH


def _sync_db_path() -> None:
    _db.DB_PATH = DB_PATH


def _delegate(func_name: str, *args: Any, **kwargs: Any) -> Any:
    _sync_db_path()
    fn: Callable[..., Any] = getattr(_db, func_name)
    return fn(*args, **kwargs)


def __getattr__(name: str) -> Any:
    if name == "DB_PATH":
        return DB_PATH
    target = getattr(_db, name)
    if callable(target):
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return _delegate(name, *args, **kwargs)

        return _wrapped
    return target


def init_db() -> Any:
    return _delegate("init_db")


def get_account_state() -> Any:
    return _delegate("get_account_state")


def save_account_state(state: dict[str, Any]) -> Any:
    return _delegate("save_account_state", state)
