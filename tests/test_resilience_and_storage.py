import asyncio

from trading_bot.core.resilience.circuit_breaker import CircuitBreaker
from trading_bot.core.resilience.retry_policy import RetryPolicy
from trading_bot.infrastructure.database.postgres_trade_repo import PostgresTradeRepository
from trading_bot.infrastructure.redis.redis_state_store import RedisStateStore


def test_circuit_breaker_basic_flow():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=0.01)
    breaker.record_failure()
    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.state.value == "open"
    assert breaker.allow_request() is False


def test_retry_policy_retries_then_succeeds():
    async def _run():
        attempts = {"count": 0}

        async def action():
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ValueError("retry")
            return "ok"

        policy = RetryPolicy(max_attempts=3, retry_delay_seconds=0)
        result = await policy.execute(action)
        assert result == "ok"

    asyncio.run(_run())


def test_storage_layers_initialize_cleanly():
    async def _run():
        state = RedisStateStore()
        repo = PostgresTradeRepository()

        await state.set("mode", "live")
        await repo.save({"symbol": "EURUSD", "status": "open"})

        assert await state.get("mode") == "live"
        assert await repo.list() == []

    asyncio.run(_run())
