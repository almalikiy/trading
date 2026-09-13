# MT5 Release Approval Template

## Release identification
- Release name / version:
- Date:
- Release owner:
- Target environment:
- Broker/account used:
- MT5 terminal ID / server:
- App version / commit hash:

---

## 1. Preconditions

- [ ] Environment validation completed and passed
- [ ] Broker config validated with `validate_brokers.py`
- [ ] Backend startup completed without startup exception
- [ ] API health endpoint is reachable
- [ ] Correct MT5 terminal and account were confirmed
- [ ] `XAUUSD` symbol is available and readable

Pass/Fail notes:
-

---

## 2. Live MT5 safety gate

### 2.1 Terminal ownership and account correctness
- [ ] Correct terminal connected
- [ ] Correct account number confirmed
- [ ] Correct server/account type confirmed
- [ ] No mismatch between intended environment and connected account

Evidence:
-

### 2.2 Startup and shutdown stability
- [ ] Backend started successfully
- [ ] API responded without error
- [ ] `Ctrl+C` shutdown completed cleanly
- [ ] No stale Python/Uvicorn processes remained

Evidence:
-

### 2.3 Keep-alive off behavior
- [ ] Keep MT5 alive set to OFF
- [ ] MT5 terminal closed manually
- [ ] MT5 did not restart automatically

Evidence:
-

### 2.4 Execution smoke test
- [ ] BUY order executed with minimal safe volume
- [ ] Order ID recorded
- [ ] Position appears in backend state
- [ ] SELL or close action executed successfully
- [ ] Position count and trade history updated correctly

Evidence:
-

### 2.5 Risk guardrails
- [ ] Max open trades / max lot / loss cap tested
- [ ] Risk blocker triggered as expected
- [ ] Trade was refused before execution
- [ ] Risk event logged clearly

Evidence:
-

### 2.6 Disconnect and recovery handling
- [ ] Disconnect/recovery simulation performed
- [ ] Backend entered degraded mode
- [ ] No new order executed while disconnected
- [ ] Recovery status was clear and logged

Evidence:
-

---

## 3. Release decision

### Overall result
- [ ] PASS
- [ ] FAIL
- [ ] HOLD / REWORK

### Decision statement
> “MT5 live safety gate passed / failed as of [date/time]. No live trading proceeds until the signoff below is recorded.”

---

## 4. Signoff

### Backend owner
Name:
Signature / date:
Comments:

### Operations / runtime owner
Name:
Signature / date:
Comments:

### Risk owner
Name:
Signature / date:
Comments:

---

## 5. Final approval

- [ ] All required tests above have been executed and passed
- [ ] No unresolved MT5 safety issues remain
- [ ] Team agrees to release / proceed with live validation
- [ ] Team agrees to hold / not proceed

Final approver:
- Name:
- Signature / date:
- Final decision:
