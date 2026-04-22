# === Real Trade Execution Logic ===
def open_real_trade(symbol, lot, trade_type):
    if not mt5.initialize():
        raise RuntimeError("MT5 not connected")
    if trade_type == 'buy':
        order_type = mt5.ORDER_TYPE_BUY
    elif trade_type == 'sell':
        order_type = mt5.ORDER_TYPE_SELL
    else:
        raise ValueError("trade_type must be 'buy' or 'sell'")
    price = mt5.symbol_info_tick(symbol).ask if trade_type == 'buy' else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 0,
        "comment": "",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    mt5.shutdown()
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"Order send failed: {result.retcode} {result.comment}")
    return {"status": "ok", "order": result._asdict()}

def close_real_trade(symbol, lot, ticket):
    if not mt5.initialize():
        raise RuntimeError("MT5 not connected")
    position = mt5.positions_get(ticket=ticket)
    if not position:
        raise RuntimeError(f"No open position with ticket {ticket}")
    pos = position[0]
    if pos.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    elif pos.type == mt5.POSITION_TYPE_SELL:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    else:
        raise RuntimeError("Unknown position type")
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 0,
        "comment": "",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    mt5.shutdown()
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"Order close failed: {result.retcode} {result.comment}")
    return {"status": "ok", "order": result._asdict()}
# =============================================
# Penjelasan singkat keyword, API, dan library:
#
# - MetaTrader5 (mt5): Library Python untuk koneksi ke aplikasi trading MetaTrader 5 (API broker). Digunakan untuk mengambil data harga pasar (OHLCV) secara real-time dari broker.
# - pandas (pd): Library utama untuk manipulasi data berbasis tabel (DataFrame). Sangat berguna untuk analisis data finansial.
# - numpy (np): Library matematika dan statistik, sering dipakai untuk operasi numerik dan simulasi data.
# - ta: Library technical analysis, menyediakan berbagai indikator trading populer (RSI, MACD, Bollinger Bands, dsb).
# - time: Modul standar Python untuk operasi waktu (jarang dipakai di script ini).
#
# Keyword penting Python:
# - def: Mendefinisikan fungsi.
# - import: Memanggil library eksternal.
# - return: Mengembalikan hasil dari fungsi.
# - if/else: Percabangan logika.
# - for: Perulangan.
# - try/except: Penanganan error/exception.
# - dict, list: Struktur data utama di Python.
#
# Fungsi utama file ini:
# - fetch_ohlcv: Mengambil data harga OHLCV dari MT5.
# - calculate_indicators: Menghitung indikator teknikal dari data OHLCV.
# - generate_signal: Membuat sinyal trading sederhana dari indikator.
# - analyze_symbol: Analisa multi-timeframe dan simulasi trading.
# =============================================

# ====== IMPORT LIBRARY DAN API ======
# MetaTrader5: Library untuk koneksi ke aplikasi trading MetaTrader 5 (API broker)
import MetaTrader5 as mt5
# pandas: Library untuk manipulasi data (DataFrame)
import pandas as pd
# numpy: Library matematika dan statistik
import numpy as np
# time: Modul standar Python untuk waktu (jarang dipakai di script ini)
import time
# ta: Library technical analysis (indikator trading)
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator

###########################################################
# Fungsi utama: Mengambil data OHLCV dari MetaTrader 5 API
# OHLCV = Open, High, Low, Close, Volume (data candlestick)
###########################################################
def fetch_ohlcv(symbol, timeframe, bars=100):
    # Mapping kode timeframe string ke konstanta MT5
    tf_map = {
        'M1': mt5.TIMEFRAME_M1,   # 1 menit
        'M5': mt5.TIMEFRAME_M5,   # 5 menit
        'M15': mt5.TIMEFRAME_M15, # 15 menit
        'M30': mt5.TIMEFRAME_M30  # 30 menit
    }
    # Inisialisasi koneksi ke MetaTrader 5
    if not mt5.initialize():
        raise RuntimeError("MT5 not connected")
    # Ambil 60 bar ekstra dari permintaan
    bars_fetch = bars + 60
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, bars_fetch)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data for {symbol} {timeframe}")
    df = pd.DataFrame(rates)
    if df.empty:
        raise RuntimeError(f"No data for {symbol} {timeframe}")
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
    df = df.astype({
        'open': float,
        'high': float,
        'low': float,
        'close': float,
        'tick_volume': int
    }, errors='ignore')
    # Kembalikan semua bar hasil fetch, frontend yang memilih bar mana yang ditampilkan
    return df

###########################################################
# Fungsi: Hitung indikator teknikal dari data OHLCV
# Menggunakan library ta (technical analysis)
###########################################################
def calculate_indicators(df):
    result = {}
    # Bollinger Bands (indikator volatilitas)
    bb = BollingerBands(df['close'])
    result['bb_upper'] = bb.bollinger_hband().iloc[-1]
    result['bb_lower'] = bb.bollinger_lband().iloc[-1]
    result['bb_mid'] = bb.bollinger_mavg().iloc[-1]
    # RSI (Relative Strength Index, momentum)
    rsi = RSIIndicator(df['close'])
    result['rsi'] = rsi.rsi().iloc[-1]
    # MACD (Moving Average Convergence Divergence, trend)
    macd = MACD(df['close'])
    result['macd'] = macd.macd().iloc[-1]
    result['macd_signal'] = macd.macd_signal().iloc[-1]
    # Stochastic Oscillator (indikator momentum)
    stoch = StochasticOscillator(df['high'], df['low'], df['close'])
    result['stoch_k'] = stoch.stoch().iloc[-1]
    result['stoch_d'] = stoch.stoch_signal().iloc[-1]
    # SMA (Simple Moving Average, rata-rata harga)
    sma = SMAIndicator(df['close'], window=14)
    result['sma'] = sma.sma_indicator().iloc[-1]
    return result

###########################################################
# Fungsi: Generate sinyal trading berdasarkan indikator
# Contoh logika: buy jika semua syarat indikator terpenuhi
###########################################################
def generate_signal(indicators, mode='real'):
    # Mode scalp: hanya cek M1 dan M5, syarat lebih longgar
    if mode == 'scalp':
        tfs = [k for k in indicators.keys() if k in ['M1', 'M5']]
        if (
            all(indicators[tf]['macd'] > indicators[tf]['macd_signal'] for tf in tfs) and
            all(indicators[tf]['rsi'] < 80 for tf in tfs)
        ):
            return 'buy'
        return 'wait'
    # Mode normal: semua TF, syarat ketat
    if (
        all(i['rsi'] < 70 for i in indicators.values()) and
        all(i['macd'] > i['macd_signal'] for i in indicators.values()) and
        all(i['bb_lower'] < i['sma'] < i['bb_upper'] for i in indicators.values())
    ):
        return 'buy'
    return 'wait'


###########################################################
# Fungsi utama: Analisa multi-timeframe dan simulasi trading
# Memanggil fetch_ohlcv dan calculate_indicators untuk tiap TF
###########################################################
def analyze_symbol(symbol, bars=60, timeframes=None, mode='real'):
    timeframes = ['M1', 'M5', 'M15', 'M30']
    indicators = {}
    errors = {}
    for tf in timeframes:
        try:
            df = fetch_ohlcv(symbol, tf)
            indicators[tf] = calculate_indicators(df)
        except Exception as e:
            errors[tf] = str(e)
    if errors:
        return {'error': 'Failed to fetch data for some timeframes', 'details': errors}
    signal = generate_signal(indicators, mode=mode)
    # --- Simulator logic ---
    if 'M1' in indicators:
        price = indicators['M1']['sma']
        sim_result = simulator.update(price, signal)
    else:
        sim_result = {}
    return {'signal': signal, 'indicators': indicators, 'simulator': sim_result}

# --- Simulator logic ---
###########################################################
# Kelas: Simulasi sederhana money management trading
# Untuk menghitung balance, PnL, open/close trade
###########################################################
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
