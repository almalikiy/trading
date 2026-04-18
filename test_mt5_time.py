import MetaTrader5 as mt5
from datetime import datetime, timezone

if not mt5.initialize():
    raise RuntimeError("MT5 not connected")

# Ambil waktu server (epoch detik) dari bar terakhir
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
if rates is not None and len(rates) > 0:
    bar_time_epoch = rates[0]['time']
    bar_time_utc = datetime.utcfromtimestamp(bar_time_epoch)
    bar_time_local = datetime.fromtimestamp(bar_time_epoch)
    print("Epoch dari bar terakhir:", bar_time_epoch)
    print("Waktu UTC:", bar_time_utc)
    print("Waktu lokal komputer:", bar_time_local)
else:
    print("Gagal mengambil data rates dari MT5.")

mt5.shutdown()