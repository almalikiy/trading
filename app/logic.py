# === MT5 Error Logging ===

from .db import log_mt5_error, get_mt5_error_log
# === Real Trade Execution Logic ===
def open_real_trade(symbol, lot, trade_type):
    if not mt5.initialize():
        log_mt5_error("MT5 not connected (open_real_trade)")
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
        log_mt5_error(f"Order send failed: {result.retcode} {result.comment}")
        raise RuntimeError(f"Order send failed: {result.retcode} {result.comment}")
    return {"status": "ok", "order": result._asdict()}

def close_real_trade(symbol, lot, ticket):
    if not mt5.initialize():
        log_mt5_error("MT5 not connected (close_real_trade)")
        raise RuntimeError("MT5 not connected")
    position = mt5.positions_get(ticket=ticket)
    if not position:
        log_mt5_error(f"No open position with ticket {ticket}")
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
        log_mt5_error(f"Order close failed: {result.retcode} {result.comment}")
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
import threading
from typing import Any
# ta: Library technical analysis (indikator trading)
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator


SUPPORTED_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
DEFAULT_SIGNAL_TIMEFRAMES = ("M1", "M5", "M15", "M30")


def normalize_timeframes(timeframes):
    if not timeframes:
        return list(DEFAULT_SIGNAL_TIMEFRAMES)
    normalized = []
    for item in timeframes:
        value = str(item or "").strip().upper()
        if value in SUPPORTED_TIMEFRAMES and value not in normalized:
            normalized.append(value)
    if len(normalized) < 2:
        return list(DEFAULT_SIGNAL_TIMEFRAMES)
    return normalized

###########################################################
# Fungsi utama: Mengambil data OHLCV dari MetaTrader 5 API
# OHLCV = Open, High, Low, Close, Volume (data candlestick)
###########################################################
def fetch_ohlcv(symbol, timeframe, bars=100, terminal_path=None):
    # Mapping kode timeframe string ke konstanta MT5
    tf_map = {
        'M1': mt5.TIMEFRAME_M1,   # 1 menit
        'M5': mt5.TIMEFRAME_M5,   # 5 menit
        'M15': mt5.TIMEFRAME_M15, # 15 menit
        'M30': mt5.TIMEFRAME_M30, # 30 menit
        'H1': mt5.TIMEFRAME_H1,   # 1 jam
        'H4': mt5.TIMEFRAME_H4,   # 4 jam
        'D1': mt5.TIMEFRAME_D1,   # 1 hari
    }
    tf = str(timeframe or "").strip().upper()
    if tf not in tf_map:
        raise RuntimeError(f"Unsupported timeframe: {timeframe}")
    # Inisialisasi koneksi ke MetaTrader 5
    initialized = False
    try:
        if terminal_path:
            initialized = mt5.initialize(path=terminal_path)
        else:
            initialized = mt5.initialize()
        if not initialized:
            raise RuntimeError("MT5 not connected")

        # Ambil 60 bar ekstra dari permintaan
        bars_fetch = bars + 60
        rates = mt5.copy_rates_from_pos(symbol, tf_map[tf], 0, bars_fetch)
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
    finally:
        if initialized:
            mt5.shutdown()

###########################################################
# Fungsi: Hitung indikator teknikal dari data OHLCV
# Menggunakan library ta (technical analysis)
###########################################################
def calculate_indicators(df, atr_period=14):
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
    atr_window = max(2, int(atr_period or 14))
    atr = AverageTrueRange(df['high'], df['low'], df['close'], window=atr_window)
    result['atr'] = atr.average_true_range().iloc[-1]
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
def analyze_symbol(symbol, bars=60, timeframes=None, mode='real', terminal_path=None, atr_period=14):
    timeframes = normalize_timeframes(timeframes)
    indicators = {}
    errors = {}
    for tf in timeframes:
        try:
            df = fetch_ohlcv(symbol, tf, bars=bars, terminal_path=terminal_path)
            indicators[tf] = calculate_indicators(df, atr_period=atr_period)
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


_signal_cache: dict[str, dict[str, Any]] = {}
_ohlcv_cache: dict[str, dict[str, Any]] = {}
_refreshing_signal: set[str] = set()
_refreshing_ohlcv: set[str] = set()
_cache_lock = threading.Lock()


def _cache_key(*parts):
    return "|".join("" if part is None else str(part) for part in parts)


def _start_background_refresh(cache_kind, key, worker):
    with _cache_lock:
        if cache_kind == "signal":
            if key in _refreshing_signal:
                return False
            _refreshing_signal.add(key)
        else:
            if key in _refreshing_ohlcv:
                return False
            _refreshing_ohlcv.add(key)

    def runner():
        try:
            worker()
        finally:
            with _cache_lock:
                if cache_kind == "signal":
                    _refreshing_signal.discard(key)
                else:
                    _refreshing_ohlcv.discard(key)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return True


def get_signal_snapshot(symbol, mode='real', terminal_path=None):
    key = _cache_key(symbol, mode, terminal_path)

    def worker():
        result = analyze_symbol(symbol, mode=mode, terminal_path=terminal_path)
        with _cache_lock:
            _signal_cache[key] = {
                "data": result,
                "updated_at": time.time(),
            }

    _start_background_refresh("signal", key, worker)

    with _cache_lock:
        snapshot = _signal_cache.get(key)

    if snapshot and snapshot.get("data"):
        payload = dict(snapshot["data"])
        payload["cached"] = True
        payload["cached_at"] = snapshot.get("updated_at")
        return payload

    return {
        "signal": "wait",
        "indicators": {},
        "simulator": {},
        "cached": False,
        "refreshing": True,
    }


def get_ohlcv_snapshot(symbol, timeframe, bars=100, terminal_path=None):
    key = _cache_key(symbol, timeframe, bars, terminal_path)

    def worker():
        df = fetch_ohlcv(symbol, timeframe, bars, terminal_path=terminal_path)
        df = df.copy()
        df["time"] = df["time"] - 3 * 3600
        df = df[["time", "open", "high", "low", "close", "tick_volume"]]
        result = df.to_dict(orient="records")
        with _cache_lock:
            _ohlcv_cache[key] = {
                "data": result,
                "updated_at": time.time(),
            }

    _start_background_refresh("ohlcv", key, worker)

    with _cache_lock:
        snapshot = _ohlcv_cache.get(key)

    if snapshot and snapshot.get("data"):
        return snapshot["data"]

    return []
