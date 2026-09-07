from trading_bot.adapters.brokers.binance_broker import BinanceBrokerAdapter
from trading_bot.adapters.brokers.mt5_broker import MT5BrokerAdapter
from trading_bot.adapters.brokers.stockbit_broker import StockbitBrokerAdapter


def test_mt5_adapter_contract():
    adapter = MT5BrokerAdapter(terminal_path="C:/MetaTrader5", login=1001, password="secret", server="Broker-Server")
    assert adapter.name == "mt5"
    assert adapter.health_check.__name__ == "health_check"


def test_binance_adapter_contract():
    adapter = BinanceBrokerAdapter()
    assert adapter.name == "binance"
    assert adapter.get_symbol_info.__name__ == "get_symbol_info"


def test_stockbit_adapter_contract():
    adapter = StockbitBrokerAdapter()
    assert adapter.name == "stockbit"
    assert adapter.get_positions.__name__ == "get_positions"
