# Trading Bot Refactor Blueprint

This repository now contains the initial clean architecture skeleton for a modular multi-market trading bot.

## Core principles

- Domain-driven design
a - Strategy does not call brokers directly
- Separate execution, risk, and market data layers
- Broker adapters share a common `BaseBroker` contract
- Configuration is environment-driven using `.env`
- Containers are prepared for local/cloud deployment

## Package structure

```text
trading_bot/
├── app/
├── core/
├── strategies/
├── risk/
├── adapters/
├── infrastructure/
├── data/
└── tests/
```

## Next refactor steps

1. Replace legacy `app/` logic with the new service-oriented architecture.
2. Implement concrete `MT5BrokerAdapter`, `BinanceBrokerAdapter`, and `StockbitBrokerAdapter`.
3. Introduce async WebSocket and REST clients for streaming market data.
4. Add Postgres and Redis persistence layers.
5. Connect API routes to the orchestration service.
6. Add integration tests and production hardening.
