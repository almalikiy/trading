from __future__ import annotations

from decimal import Decimal
from typing import Any

from trading_bot.adapters.brokers.broker_factory import BrokerFactory
from trading_bot.infrastructure.config.settings import get_settings


class OperationalAlertService:
    def __init__(self) -> None:
        self._alerts: list[dict[str, Any]] = []

    def add(self, code: str, message: str, level: str = "warning", **metadata: Any) -> dict[str, Any]:
        payload = {"code": code, "message": message, "level": level, **metadata}
        self._alerts.append(payload)
        return payload

    def snapshot(self) -> list[dict[str, Any]]:
        return [alert.copy() for alert in self._alerts]


class ProductionGuardService:
    def __init__(
        self,
        max_lot: Decimal | float | None = None,
        max_daily_loss_pct: Decimal | float | None = None,
        max_drawdown_pct: Decimal | float | None = None,
        min_margin_buffer_pct: Decimal | float | None = None,
        max_open_positions: int | None = None,
        kill_switch_enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.max_lot = Decimal(str(max_lot)) if max_lot is not None else Decimal(str(settings.max_lot))
        self.max_daily_loss_pct = Decimal(str(max_daily_loss_pct)) if max_daily_loss_pct is not None else Decimal(str(settings.max_daily_loss_pct))
        self.max_drawdown_pct = Decimal(str(max_drawdown_pct)) if max_drawdown_pct is not None else Decimal(str(settings.max_drawdown_pct))
        self.min_margin_buffer_pct = Decimal(str(min_margin_buffer_pct)) if min_margin_buffer_pct is not None else Decimal(str(settings.min_margin_buffer_pct))
        self.max_open_positions = max_open_positions if max_open_positions is not None else settings.max_open_positions
        self.kill_switch_enabled = settings.kill_switch_enabled if kill_switch_enabled is None else bool(kill_switch_enabled)
        self.alert_service = OperationalAlertService()

    async def validate_order_request(
        self,
        broker_name: str,
        symbol: str,
        side: str,
        volume: Decimal | float,
        max_lot: Decimal | float | None = None,
        max_daily_loss_pct: Decimal | float | None = None,
        max_drawdown_pct: Decimal | float | None = None,
        min_margin_buffer_pct: Decimal | float | None = None,
        daily_loss_pct: Decimal | float | None = None,
        current_drawdown_pct: Decimal | float | None = None,
        max_open_positions: int | None = None,
        kill_switch_enabled: bool | None = None,
    ) -> dict[str, Any]:
        self.alert_service = OperationalAlertService()
        broker = BrokerFactory.create(str(broker_name).strip())
        errors: list[str] = []

        active_kill_switch = self.kill_switch_enabled if kill_switch_enabled is None else bool(kill_switch_enabled)
        if active_kill_switch:
            errors.append("kill_switch_enabled")
            self.alert_service.add("kill_switch_enabled", "Trading is disabled by operational kill switch", level="critical")

        try:
            if hasattr(broker, "connected") and not getattr(broker, "connected", False):
                await broker.connect()
            is_healthy = await broker.health_check()
        except Exception as exc:  # pragma: no cover - runtime dependency
            is_healthy = False
            errors.append(f"broker_connection_failed: {exc}")

        if not is_healthy:
            errors.append("broker_not_ready")
            self.alert_service.add("broker_not_ready", "Broker health check failed", level="critical")

        symbol_name = str(symbol or "").strip()
        if not symbol_name:
            errors.append("symbol_required")
            self.alert_service.add("symbol_required", "Symbol must be provided", level="critical")

        side_value = str(side or "").upper()
        if side_value not in {"BUY", "SELL"}:
            errors.append("invalid_side")
            self.alert_service.add("invalid_side", f"Unsupported trade side: {side}", level="critical")

        volume_value = Decimal(str(volume))
        lot_limit = Decimal(str(max_lot)) if max_lot is not None else self.max_lot
        if volume_value <= 0:
            errors.append("volume_must_be_positive")
            self.alert_service.add("volume_must_be_positive", "Order volume must be positive", level="critical")
        if volume_value > lot_limit:
            errors.append(f"max_lot_exceeded: volume {volume_value} > {lot_limit}")
            self.alert_service.add(
                "max_lot_exceeded",
                f"Requested volume {volume_value} exceeds configured cap {lot_limit}",
                level="critical",
            )

        try:
            account = await broker.get_account_summary()
        except Exception as exc:  # pragma: no cover - runtime dependency
            errors.append(f"account_summary_unavailable: {exc}")
            self.alert_service.add("account_summary_unavailable", str(exc), level="critical")
            account = None

        if account is not None:
            placeholder_account = (
                account.balance == 0
                and account.equity == 0
                and account.margin_used == 0
                and account.free_margin == 0
            )

            if not placeholder_account:
                if account.equity <= 0:
                    errors.append("equity_not_positive")
                    self.alert_service.add("equity_not_positive", "Equity is not positive", level="critical")
                if account.free_margin <= 0:
                    errors.append("free_margin_not_positive")
                    self.alert_service.add("free_margin_not_positive", "Free margin is not positive", level="critical")

                margin_buffer_pct = Decimal("0")
                if account.equity > 0:
                    margin_buffer_pct = (account.free_margin / account.equity) * Decimal("100")
                threshold = Decimal(str(min_margin_buffer_pct)) if min_margin_buffer_pct is not None else self.min_margin_buffer_pct
                if margin_buffer_pct < threshold:
                    errors.append(f"margin_buffer_too_low: {margin_buffer_pct} < {threshold}")
                    self.alert_service.add(
                        "margin_buffer_too_low",
                        f"Margin buffer {margin_buffer_pct}% is below required threshold {threshold}%",
                        level="critical",
                    )
            else:
                self.alert_service.add(
                    "placeholder_account_summary",
                    "Broker account summary is placeholder data; live margin checks skipped until broker is connected to a real account.",
                    level="warning",
                )

        if daily_loss_pct is not None:
            loss_limit = Decimal(str(max_daily_loss_pct)) if max_daily_loss_pct is not None else self.max_daily_loss_pct
            if Decimal(str(daily_loss_pct)) > loss_limit:
                errors.append(f"daily_loss_limit_exceeded: {daily_loss_pct} > {loss_limit}")
                self.alert_service.add(
                    "daily_loss_limit_exceeded",
                    f"Current daily loss {daily_loss_pct}% exceeds cap {loss_limit}%",
                    level="critical",
                )

        effective_drawdown_limit = Decimal(str(max_drawdown_pct)) if max_drawdown_pct is not None else self.max_drawdown_pct
        effective_current_drawdown = Decimal(str(current_drawdown_pct)) if current_drawdown_pct is not None else Decimal("0")
        if current_drawdown_pct is not None:
            if effective_current_drawdown > effective_drawdown_limit:
                errors.append(f"drawdown_limit_exceeded: {effective_current_drawdown} > {effective_drawdown_limit}")
                self.alert_service.add(
                    "drawdown_limit_exceeded",
                    f"Current drawdown {effective_current_drawdown}% exceeds configured limit {effective_drawdown_limit}%",
                    level="critical",
                )

        if max_open_positions is not None:
            limit = max_open_positions
            if int(max_open_positions) < 0:
                errors.append("max_open_positions_invalid")
                self.alert_service.add("max_open_positions_invalid", "Open positions limit must be non-negative", level="critical")
            if int(max_open_positions) == 0:
                errors.append("max_open_positions_zero")
                self.alert_service.add("max_open_positions_zero", "Open positions limit is zero; no new trades allowed", level="critical")

        try:
            positions = await broker.get_positions()
        except Exception as exc:  # pragma: no cover - runtime dependency
            errors.append(f"positions_unavailable: {exc}")
            self.alert_service.add("positions_unavailable", str(exc), level="warning")
            positions = []

        if max_open_positions is not None:
            current_positions = len(positions or [])
            if current_positions >= int(max_open_positions):
                errors.append(f"max_open_positions_reached: {current_positions} >= {max_open_positions}")
                self.alert_service.add(
                    "max_open_positions_reached",
                    f"Broker already has {current_positions} open positions, which meets the configured limit of {max_open_positions}.",
                    level="critical",
                )

        try:
            info = await broker.get_symbol_info(symbol_name)
        except Exception as exc:  # pragma: no cover - runtime dependency
            errors.append(f"symbol_info_unavailable: {exc}")
            self.alert_service.add("symbol_info_unavailable", str(exc), level="critical")
            info = None

        if info is not None and info.get("status") not in {None, "available", "ok", "ready", "skeleton"}:
            errors.append(f"symbol_not_available: {symbol_name}")
            self.alert_service.add("symbol_not_available", f"Symbol {symbol_name} is not available or marked inactive", level="critical")
        elif info is not None and info.get("status") == "skeleton":
            self.alert_service.add(
                "symbol_placeholder_mode",
                f"Symbol {symbol_name} metadata is in placeholder mode; live validation will be strict only when broker is connected to a real account.",
                level="warning",
            )

        return {
            "allowed": not errors,
            "symbol": symbol_name,
            "broker": str(broker_name).strip(),
            "errors": errors,
            "alerts": self.alert_service.snapshot(),
            "risk": {
                "max_lot": str(lot_limit),
                "max_daily_loss_pct": str(max_daily_loss_pct if max_daily_loss_pct is not None else self.max_daily_loss_pct),
                "max_drawdown_pct": str(max_drawdown_pct if max_drawdown_pct is not None else self.max_drawdown_pct),
                "current_drawdown_pct": str(current_drawdown_pct if current_drawdown_pct is not None else effective_current_drawdown),
                "min_margin_buffer_pct": str(min_margin_buffer_pct if min_margin_buffer_pct is not None else self.min_margin_buffer_pct),
                "kill_switch_enabled": str(active_kill_switch).lower(),
            },
        }
