# NeuralMT5 Real-Host Validation Preparation

## Safety rule

Do not begin with LIVE mode. Keep:

```env
TRADING_MODE=analysis
LIVE_EXECUTION_ENABLED=false
LIVE_READINESS_ACKNOWLEDGED=false
LIVE_FAULT_INJECTION_PASSED=false
LIVE_SOAK_TEST_PASSED=false
```

No script in `tools/` changes these flags automatically.

## Host prerequisites

Use a Windows host supported by the MetaTrader5 Python package, the same MT5 terminal/account intended for validation, and a demo account first. Install with:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-mt5.txt
copy .env.example .env
```

Fill MT5 connection values and canonical symbols in `.env`. Keep `TRADING_MODE=analysis`.

## Stage 0 — resolver and training-data diagnostics

Before any soak or live-readiness test, verify that canonical symbols resolve to the intended broker symbols and that training data is actually usable:

```powershell
python train.py --diagnose
```

Review `storage/reports/training_data_diagnostics.json`. For each configured canonical symbol, confirm:

- the selected `broker_symbol` is the intended tradable symbol;
- replay/playback/custom symbols are rejected;
- `trade_mode` allows opening new positions;
- resolver confidence meets `MIN_SYMBOL_RESOLUTION_CONFIDENCE`;
- HTF/MTF/LTF history counts meet minimum requirements;
- feature and synchronized-sequence counts are non-zero;
- class distribution is not degenerate.

For brokers that expose multiple valid variants, keep the canonical symbol in `SYMBOLS` and use an explicit override only when needed, for example:

```env
SYMBOLS=XAUUSD
SYMBOL_XAUUSD=XAUUSD.vx
SYMBOL_EXCLUDE_TOKENS=REPLAY,REPALY,PLAYBACK
```

Manual overrides remain subject to the same safety checks; they cannot force a replay/custom/non-openable symbol. Do not lower the global resolver confidence threshold merely to make an incorrect candidate pass.

## Stage A — read-only host preflight

Run:

```powershell
python tools/real_host_preflight.py
```

Expected artifact:

`storage/reports/real_host_preflight.json`

This checks connection, symbol resolution, bid/ask availability, closed-candle history for HTF/MTF/LTF, terminal/account permissions, broker execution specifications, and local model/scaler artifacts. It sends **zero orders**.

## Stage B — analysis soak

With a real trained Champion + paired scaler available:

```powershell
python tools/host_soak.py --cycles 500
```

Review `storage/reports/host_soak.json`, runtime database, system events, memory growth, reconnect behavior, and dashboard behavior. Increase duration only after short runs are clean.

## Stage C — paper-mode soak

Change only:

```env
TRADING_MODE=paper
```

Repeat the soak. Verify deterministic plans, no broker order calls, persistent restart state, duplicate claims, daily risk state, and dashboard isolation.

## Stage D — mandatory fault-injection matrix

Perform these tests on a demo account/terminal and retain timestamped evidence. Do not set the pass flag merely because an exception was caught.

1. Terminal closed before startup → fail closed.
2. Terminal disconnected during analysis → bounded reconnect; no new order.
3. Disconnect immediately after a broker send → reconciliation must determine broker truth before another entry.
4. Process killed after durable order claim but before broker response → duplicate entry must not occur on restart.
5. Process killed after broker fill but before local trade persistence → broker-history reconciliation must recover the fill.
6. Partial fill → remaining exposure and broker position identity reconciled; no false full-fill state.
7. Requote/price changed → slippage/preflight rejection is auditable.
8. Abnormal spread → risk/preflight veto.
9. Broker stops-level rejection → no retry loop that weakens SL.
10. Freeze-level scenario → modifications/closure handled safely.
11. MT5 terminal restart while a position is open → monitoring/reconciliation resumes.
12. Dashboard stopped/crashed → position safety loop continues.
13. Database temporarily locked/unavailable → no duplicate broker action and critical failure is visible.
14. Model/scaler corrupted or mismatched → startup fails closed.
15. Host clock/tick timestamp skew over configured limit → live gate fails.
16. Session close / `FORCE_FLAT_TIME` → no new entry and existing intraday position is handled per policy.
17. Netting account mapping → order/deal/position identity reconciles correctly.
18. Hedging account mapping → multiple same-symbol positions reconcile without guessing.

Several items above intentionally expose current blockers from the final audit. A failed test is evidence to fix the implementation, not a reason to set the flag.

## Stage E — minimum live-readiness evidence bundle

Retain at least:

- exact git/package hash;
- `.env` snapshot with secrets redacted;
- model metadata + weights hash;
- scaler metadata + hash;
- dataset/config hashes;
- `real_host_preflight.json`;
- soak reports;
- fault-injection report with pass/fail per case;
- MT5 terminal/account/build information;
- broker symbol specifications;
- reconciliation report before/after each restart test;
- test suite output;
- any broker trade/deal exports used to verify persistence.

Only after all mandatory cases pass should a human review whether to set:

```env
LIVE_FAULT_INJECTION_PASSED=true
LIVE_SOAK_TEST_PASSED=true
```

Then separately acknowledge readiness and enable live execution. Do not combine these changes with code changes or model promotion.
