# MT5 Live Safety Runbook

## Status

This runbook is the operational gate for any go-live decision. It must be executed in order. Do not skip steps. If any step fails, stop the process and do not continue to the next step.

Current project status:
- Unit tests are green.
- Runtime and dashboard smoke checks are stable.
- This is not yet a go-live certification without live MT5 validation.

---

## 0) Preparation

Run this in PowerShell from the project root:

```powershell
Set-Location "D:\development\trading"
Get-Location
$env:PYTHONPATH = "."
```

Expected result:
- Current directory is `D:\development\trading`
- No errors

If there are stale Python/Uvicorn processes from previous runs, clean them first:

```powershell
taskkill /F /IM python.exe /IM pythonw.exe /IM uvicorn.exe 2>nul
```

Expected result:
- No fatal error
- Or only a benign “No tasks found” style response

Pass condition:
- stale processes cleared or confirmed not active

Fail condition:
- old backend processes are still running and expected to be cleaned

---

## 1) Environment and broker validation

Run:

```powershell
set PYTHONPATH=. ; .\.venv\Scripts\python.exe validate_brokers.py
```

Expected result:
- No traceback
- Broker target, environment, account, and symbol validation all pass
- Final output indicates success or valid configuration

Pass condition:
- correct broker and environment are detected
- no mismatch warning

Fail condition:
- wrong broker/account or invalid symbol
- configuration mismatch with target environment

---

## 2) Backend startup validation

Run:

```powershell
cd /d D:\development\trading
.\.venv\Scripts\python.exe -m uvicorn trading_bot.app.main:app --host 0.0.0.0 --port 8001
```

Expected result:
- Uvicorn starts successfully
- Logs show startup completion and the server is listening on port 8001
- No crash loop, no startup error, no binding failure

Pass condition:
- backend is serving on `http://0.0.0.0:8001`

Fail condition:
- port already in use
- startup exits immediately
- unhandled exception at startup

---

## 3) API health validation

Open a second PowerShell terminal and run:

```powershell
Invoke-WebRequest http://localhost:8001/openapi.json
```

Expected result:
- HTTP 200
- JSON output from FastAPI/OpenAPI schema is returned

Optional browser check:
- open `http://localhost:8001/docs`

Expected result:
- Swagger UI loads correctly

Pass condition:
- API responds properly and schema is available

Fail condition:
- request fails
- response is empty or error page

---

## 4) MT5 terminal ownership validation

From the backend runtime or control panel, confirm all of the following:
- correct MT5 terminal instance is connected
- correct account number is active
- correct server and account type are selected
- this matches the intended live/demo environment exactly

Expected result:
- backend reports the intended terminal is connected
- account summary matches the designated environment

Pass condition:
- MT5 account and terminal identity are correct

Fail condition:
- wrong account or wrong terminal is selected
- data comes from another environment

---

## 5) Symbol readiness validation for XAUUSD

Check the backend MT5 status or the terminal itself:

```powershell
Invoke-RestMethod http://localhost:8001/mt5/status
```

Expected result:
- MT5 is connected
- `XAUUSD` is available in symbol list
- bid/ask, spread, and tick data are valid and current

If using the MT5 terminal directly:
- confirm `XAUUSD` is selected successfully
- quote data is refreshed
- spread and price values are non-zero and actionable

Pass condition:
- symbol is ready for trading and market data is valid

Fail condition:
- symbol unavailable
- spread is invalid or zero
- tick data is stale or missing

---

## 6) Live order smoke test – BUY

Use the smallest safe lot size allowed by the broker, typically `0.01` or the broker minimum.

Operational steps:
1. Submit a BUY market order with minimal safe volume
2. Verify the order is accepted
3. Verify fill or execution status
4. Verify an open position is created in backend state
5. Check that the order log is clear and traceable

Expected result:
- order exists and is accepted
- one new open position appears
- backend state matches the MT5 execution state
- no duplicate order IDs

Pass condition:
- order executes with correct lifecycle and state update

Fail condition:
- order rejected without clear reason
- trade execution is stale or duplicated
- backend and broker disagree on position state

---

## 7) Live order smoke test – SELL / close

After the BUY position is active:
1. Submit a SELL order or close action to exit the position
2. Verify the trade closes properly
3. Confirm the open position count decreases
4. Verify close event is captured in logs and API state

Expected result:
- position closes correctly
- trade history updates to reflect the close
- state is consistent in both backend and broker adapter

Pass condition:
- exit path works without discrepancy

Fail condition:
- order stays open unexpectedly
- close event is missing
- backend and MT5 diverge

---

## 8) Risk guardrail validation

Deliberately trigger a guard condition using a known low threshold:
- max open trades
- max lot
- daily loss cap
- margin threshold
- symbol blocklist

Then submit a new order.

Expected result:
- backend blocks execution before route enters MT5
- blocker reason is logged clearly
- no actual new trade is opened

Pass condition:
- risk hard stop is enforced exactly as designed

Fail condition:
- trade still executes despite risk limit
- silent behavior or ambiguous rejection without logs

---

## 9) MT5 keep-alive OFF validation

Confirm the app is configured with MT5 keep-alive OFF.

Then:
1. manually close the MT5 terminal
2. wait several minutes
3. verify whether the terminal reappears automatically

Expected result:
- no auto-restart loop while keep-alive is OFF
- no background process reopens MT5 without operator action

Pass condition:
- MT5 stays off when configured off

Fail condition:
- terminal reopens unexpectedly or restarts repeatedly

---

## 10) Disconnect and recovery validation

Simulate a temporary broker disconnect or connectivity outage.

Expected result:
- app transitions to degraded mode
- no new orders are allowed while disconnected
- health status clearly shows the outage
- logs capture issue and recovery path

Pass condition:
- backend responds safely to disconnects

Fail condition:
- app keeps trading while disconnected
- silent failure with no clear status

---

## 11) Clean shutdown validation with Ctrl+C

In the backend terminal, press `Ctrl+C` once.

Expected result:
- server shuts down cleanly
- no hanging process
- no orphaned Python/Uvicorn process remains

Check with:

```powershell
tasklist /FI "IMAGENAME eq python.exe" /FI "IMAGENAME eq pythonw.exe" /FI "IMAGENAME eq uvicorn.exe"
```

Expected result:
- no backend process is still active

Pass condition:
- clean shutdown verified

Fail condition:
- shutdown hangs or process remains alive

---

## 12) Go-live signoff

Only proceed if every item above passed.

Required signoff from:
- backend owner
- operations owner
- risk owner

Final signoff statement:

> “MT5 live safety gate passed. No live deployment proceeds without this signoff.”

If any test failed, the correct state is:
- not ready for go-live
- continue fixing the failing safety item
- do not begin wider live trading

---

## Quick pass/fail checklist

- [ ] broker validation passed
- [ ] backend startup passed
- [ ] API health passed
- [ ] MT5 terminal ownership verified
- [ ] `XAUUSD` symbol validated
- [ ] BUY smoke test passed
- [ ] SELL/close smoke test passed
- [ ] risk guardrail test passed
- [ ] keep-alive OFF validated
- [ ] disconnect recovery validated
- [ ] clean shutdown validated
- [ ] required signoff recorded

---

## Final note

A green unit test suite is necessary but not sufficient. The live MT5 gate above is the actual release condition before any wider production deployment or real-money activity.
