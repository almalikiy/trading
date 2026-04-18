import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator

# Helper: fetch OHLCV data from MT5
def fetch_ohlcv(symbol, timeframe, bars=100):
    tf_map = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30
    }
    if not mt5.initialize():
        raise RuntimeError("MT5 not connected")
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data for {symbol} {timeframe}")
    df = pd.DataFrame(rates)
    if df.empty:
        raise RuntimeError(f"No data for {symbol} {timeframe}")
    # Pastikan hanya kolom yang diperlukan dan urut
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['time_utc'] = df['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    import tzlocal
    local_tz = tzlocal.get_localzone()
    # Format ISO8601 lengkap dengan offset timezone
    df['time_local'] = df['time'].dt.tz_convert(local_tz).dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    # Pilih dan urutkan kolom sesuai kebutuhan frontend
    columns = ['time_utc', 'time_local', 'open', 'high', 'low', 'close', 'tick_volume']
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df = df[columns]
    # Konversi tipe data ke Python native agar serialisasi JSON valid
    df = df.astype({
        'open': float,
        'high': float,
        'low': float,
        'close': float,
        'tick_volume': int
    }, errors='ignore')
    return df

# Helper: calculate all indicators

def calculate_indicators(df):
    result = {}
    # Bollinger Bands
    bb = BollingerBands(df['close'])
    result['bb_upper'] = bb.bollinger_hband().iloc[-1]
    result['bb_lower'] = bb.bollinger_lband().iloc[-1]
    result['bb_mid'] = bb.bollinger_mavg().iloc[-1]
    # RSI
    rsi = RSIIndicator(df['close'])
    result['rsi'] = rsi.rsi().iloc[-1]
    # MACD
    macd = MACD(df['close'])
    result['macd'] = macd.macd().iloc[-1]
    result['macd_signal'] = macd.macd_signal().iloc[-1]
    # Stochastic RSI
    stoch = StochasticOscillator(df['high'], df['low'], df['close'])
    result['stoch_k'] = stoch.stoch().iloc[-1]
    result['stoch_d'] = stoch.stoch_signal().iloc[-1]
    # SMA (default window 14)
    sma = SMAIndicator(df['close'], window=14)
    result['sma'] = sma.sma_indicator().iloc[-1]
    return result

# Helper: generate signal based on indicator alignment
def generate_signal(indicators):
    # Example: all RSI < 70, MACD > signal, price above SMA, price near BB lower
    if (
        all(i['rsi'] < 70 for i in indicators.values()) and
        all(i['macd'] > i['macd_signal'] for i in indicators.values()) and
        all(i['bb_lower'] < i['sma'] < i['bb_upper'] for i in indicators.values())
    ):
        return 'buy'
    return 'wait'


# Main: fetch and analyze all timeframes
def analyze_symbol(symbol, bars=60, timeframes=None, mode='real'):
    timeframes = ['M1', 'M5', 'M15', 'M30']
    indicators = {}
    errors = {}
    for tf in timeframes:
        try:
            df = fetch_ohlcv(symbol, tf)
            if mode == 'simulasi':
                # Simulasikan data OHLCV dan indikator (dummy, random walk, dsb)
                import numpy as np
                import pandas as pd
                np.random.seed(42)
                base = 2000
                times = pd.date_range(end=pd.Timestamp.utcnow(), periods=bars, freq='1min')
                prices = base + np.cumsum(np.random.randn(bars))
                df = pd.DataFrame({
                    'time': times,
                    'open': prices + np.random.randn(bars),
                    'high': prices + np.abs(np.random.randn(bars)),
                    'low': prices - np.abs(np.random.randn(bars)),
                    'close': prices,
                    'tick_volume': np.random.randint(100, 200, bars)
                })
                for tf in timeframes:
                    # Untuk TF selain M1, lakukan resample
                    if tf == 'M1':
                        dftf = df.copy()
                    else:
                        rule = tf.replace('M', 'T')
                        dftf = df.resample(rule, on='time').agg({
                            'open': 'first',
                            'high': 'max',
                            'low': 'min',
                            'close': 'last',
                            'tick_volume': 'sum'
                        }).dropna().reset_index()
                    indicators = calculate_indicators(dftf)
                    results[tf] = indicators
                signal = generate_signal(results)
                sim = SignalSimulator(signal)
                return {'signal': signal, 'indicators': results, 'sim': sim.get_state()}
            indicators[tf] = calculate_indicators(df)
        except Exception as e:
            errors[tf] = str(e)
    if errors:
        return {'error': 'Failed to fetch data for some timeframes', 'details': errors}
    signal = generate_signal(indicators)
    # --- Simulator logic ---
    if 'M1' in indicators:
        price = indicators['M1']['sma']
        sim_result = simulator.update(price, signal)
    else:
        sim_result = {}
    return {'signal': signal, 'indicators': indicators, 'simulator': sim_result}

# --- Simulator logic ---
class SignalSimulator:
    def __init__(self):
        self.balance = 1000.0
        self.last_signal = None
        self.last_price = None
        self.open_trade = False
        self.pnl = 0.0

    def update(self, price, signal):
        if signal == 'buy' and not self.open_trade:
            self.last_price = price
            self.open_trade = True
            self.last_signal = 'buy'
        elif signal == 'wait' and self.open_trade:
            self.pnl = price - self.last_price
            self.balance += self.pnl
            self.open_trade = False
        return {'balance': self.balance, 'open_trade': self.open_trade, 'pnl': self.pnl}

simulator = SignalSimulator()
