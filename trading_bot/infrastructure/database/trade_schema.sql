CREATE TABLE IF NOT EXISTS trade_events (
    id SERIAL PRIMARY KEY,
    broker VARCHAR(32),
    symbol VARCHAR(32),
    side VARCHAR(16),
    volume NUMERIC(18, 8),
    status VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_quotes (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32),
    bid NUMERIC(18, 8),
    ask NUMERIC(18, 8),
    last NUMERIC(18, 8),
    source VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
