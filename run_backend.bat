@echo off
setlocal
cd /d "D:\development\trading"
del task.log 2>nul

:: 1. Hentikan proses Uvicorn/py yang masih memegang port 8001
powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn.*trading_bot\.app\.main:app|python.*uvicorn.*trading_bot\.app\.main:app|python.*trading_bot\.app\.main:app' }; foreach ($p in $procs) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {} }"

:: 2. Tunggu supaya socket benar-benar dibebaskan
timeout /t 2 /nobreak >nul

:: 3. Jalankan backend tanpa --reload agar tidak memunculkan duplicate worker dan port clash
start /b "trading_backend" "D:\development\trading\.venv\Scripts\python.exe" -m uvicorn trading_bot.app.main:app --host 0.0.0.0 --port 8001 --workers 1 >> "D:\development\trading\task.log" 2>&1
