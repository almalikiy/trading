@echo off
cd /d D:\development\trading
del task.log
:: 1. Hentikan semua proses pythonw/uvicorn yang mungkin masih mengunci port 8001
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python.exe 2>nul

:: 2. Tunggu 2 detik agar port benar-benar terbebas oleh sistem
timeout /t 2 /nobreak >nul

:: 3. Jalankan Uvicorn dengan pythonw dan redirect output ke task.log (mode append >)
start /b D:\development\trading\.venv\Scripts\pythonw.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001 >> D:\development\trading\task.log 2>&1