# NeuralMT5

**Local, deterministic, broker-aware neural trading system for MetaTrader 5.**

NeuralMT5 is a modular Python + MetaTrader 5 research and execution framework for scalping/intraday workflows. It combines broker-aware market data handling, point-in-time multi-timeframe features, a locally trained neural network, deterministic risk and execution controls, auditable journaling, controlled Champion/Challenger learning, and a real-time dashboard.

The system is intentionally designed around **capital preservation, reproducibility, risk control, execution correctness, and auditability**. If the system cannot establish a sufficiently strong and executable edge, the correct decision is **HOLD / NO TRADE**.

> [!WARNING]
> **NeuralMT5 is not self-certified for LIVE trading.**
> The software implementation and automated regression baseline are complete, but real MT5 broker/host fault-injection and long-duration soak validation must still be performed on the actual trading host. LIVE execution is disabled by default.

---

## Project Status

| Area | Status |
|---|---|
| Market Intelligence | Implemented |
| Local Neural Brain | Implemented |
| Risk & Execution | Implemented |
| Memory & Evolution | Implemented |
| Dashboard & API | Implemented |
| Integrated analysis/paper runtime | Implemented |
| Software live-readiness controls | Implemented |
| Automated regression baseline | **134 tests passing** |
| Real MT5 broker/host validation | **Pending** |
| LIVE self-certification | **No** |

Current audit status: [`docs/FINAL_FULL_PROJECT_AUDIT.md`](docs/FINAL_FULL_PROJECT_AUDIT.md)

---

## What NeuralMT5 Contains

NeuralMT5 implements the complete software-side lifecycle below:

```text
MetaTrader 5
    ↓
Broker & Symbol Discovery
    ↓
Market Data Validation
    ↓
Point-in-Time HTF / MTF / LTF Features
    ↓
Structure / Regime / Orderflow Proxy
    ↓
Local Multi-Timeframe Neural Brain
    ↓
BUY / SELL / HOLD
    ↓
Brainflow Evidence Aggregation
    ↓
Deterministic Entry / SL / TP / RR
    ↓
Risk Firewall
    ↓
Analysis / Paper / gated LIVE Execution
    ↓
Position Monitoring & Reconciliation
    ↓
Journal / Dataset / Backtest / Walk-Forward
    ↓
Champion / Challenger / Shadow / Drift
    ↓
Dashboard & Audit Trail
```

The dashboard observes and controls safe runtime state, but it is **not a trading decision layer** and it cannot directly call MT5 `order_send`.

---

## Core Design Principles

### 1. No external decision model

Trading decisions are not delegated to OpenAI, Gemini, Claude, pretrained trading models, copy-trading services, external signal APIs, or third-party BUY/SELL feeds.

The neural model is:

- initialized locally;
- trained locally;
- stored locally;
- loaded locally;
- inferred locally;
- versioned together with its scaler, feature schema, dataset, config, and hashes.

PyTorch is used as a mathematical/training framework, not as a source of pretrained trading intelligence.

### 2. Deterministic risk has final authority

The neural layer proposes an opportunity. It does **not** have authority to bypass the Risk Firewall.

```text
Neural opportunity → Layer 3 validation → ALLOW or REJECT
```

`REJECTED` is final for that opportunity.

### 3. NO SL = NO TRADE

A valid trade must have a deterministic stop loss before execution. Entry, SL, TP, RR, lot size, spread, slippage, broker stop constraints, exposure, session state, and risk limits are validated before an order may be sent.

### 4. Point-in-time only

Features may only use information available at the decision timestamp. The project explicitly guards against:

- future candles;
- centered rolling leakage;
- future-confirmed swing leakage;
- target leakage;
- whole-dataset scaler fitting;
- overlapping split leakage without purge/embargo;
- same-bar optimistic backtest entry.

### 5. Broker-aware, not suffix-hardcoded

Users configure canonical symbols such as:

```text
XAUUSD
EURUSD
GBPUSD
USDJPY
```

The resolver can match broker-specific variants such as:

```text
XAUUSD
XAUUSDm
XAUUSD.m
XAUUSD.vx
XAUUSDpro
GOLD
```

Resolution considers symbol identity plus broker metadata. Ambiguous resolution produces **NO TRADE** rather than guessing.

---


# Documentation Maintenance Policy

Documentation is part of the implementation contract. Any change that affects user/developer behavior must update the relevant documentation in the same change set. This includes new or changed:

- CLI commands and workflows;
- `.env` keys/defaults;
- training, promotion, forward-test, backtest, or live-readiness behavior;
- API/WebSocket endpoints;
- broker/symbol resolution rules;
- risk, execution, reconciliation, or recovery behavior;
- model/scaler/dataset artifact formats or compatibility rules;
- dashboard controls;
- install/runtime dependencies.

At minimum, keep `README.md`, `.env.example`, `docs/FINAL_FULL_PROJECT_AUDIT.md`, and `docs/REAL_HOST_VALIDATION.md` synchronized when the affected topic belongs there. Historical implementation notes belong in Git history rather than new phase-history documents.

---

# Architecture

NeuralMT5 uses four trading domains.

## Layer 1 — Market Intelligence

Directory: [`layer1_market/`](layer1_market)

Responsibilities:

- MT5 connectivity abstraction;
- broker specification discovery;
- canonical-to-broker symbol resolution;
- OHLC/tick retrieval;
- stale/incomplete/malformed data rejection;
- generic timeframe handling;
- point-in-time feature engineering;
- market structure;
- market regime;
- orderflow-derived proxies;
- synchronized HTF / MTF / LTF sequences.

Important distinction: tick activity, spread dynamics, bid/ask movement, rejection, absorption-like behavior, and imbalance-like behavior are treated as **derived proxies** unless real market depth data is actually available.

## Layer 2 — Local Neural Brain

Directory: [`layer2_brain/`](layer2_brain)

Baseline architecture:

```text
HTF sequence → Conv1D → GRU ─┐
MTF sequence → Conv1D → GRU ─┼→ Fusion → Multi-task heads
LTF sequence → Conv1D → GRU ─┘
```

Outputs include:

- BUY probability;
- SELL probability;
- HOLD probability;
- setup quality;
- direction confidence;
- expected favorable excursion;
- expected adverse excursion.

All semantic scores use the normalized range `0.0 .. 1.0`.

The scaler is fitted on training data only. Feature order is persisted with the scaler/model artifact and mismatches fail closed.

### Brainflow

Brainflow aggregates evidence from:

```text
HTF strength
MTF quality
LTF quality
structure
orderflow
regime
momentum
neural confidence
```

Configured weights must sum to `1.0`.

Direction selection is **not** plain `argmax`. Minimum direction score, direction margin, confidence, and Brainflow thresholds must all pass. Ambiguous predictions return `HOLD`.

## Layer 3 — Risk & Execution

Directory: [`layer3_execution/`](layer3_execution)

Responsibilities:

- current-market revalidation;
- deterministic entry pricing;
- deterministic SL/TP;
- tick-size normalization;
- RR validation;
- broker-aware position sizing;
- Risk Firewall vetoes;
- execution preflight;
- duplicate-order prevention;
- native MT5 `order_check` / `order_send` isolation;
- order/deal/position identity tracking;
- partial-fill handling;
- active-position monitoring;
- force-flat handling;
- broker reconciliation;
- restart recovery.

Position sizing uses the broker's actual `tick_size`, `tick_value`, `volume_min`, `volume_max`, and `volume_step`. If the broker's minimum lot already exceeds the allowed risk budget, the trade is rejected.

Risk checks include:

- risk per trade;
- daily risk/loss limits;
- consecutive losses;
- maximum open positions;
- total exposure;
- correlated currency exposure;
- spread;
- slippage;
- session/cutoff state;
- stops/freeze constraints;
- broker execution capability.

## Layer 4 — Memory & Evolution

Directory: [`layer4_learning/`](layer4_learning)

Responsibilities:

- immutable observations;
- post-horizon labels;
- MFE / MAE tracking;
- deterministic dataset versioning;
- chronological train/validation/test split;
- purge and embargo;
- historical pipeline backtest;
- walk-forward validation;
- Challenger evaluation;
- shadow comparison;
- drift detection;
- Champion registry;
- explicit promotion audit.

Training produces a **Challenger**, never an automatic replacement for the Champion.

`AUTO_PROMOTION_ENABLED=false` is the safe default. Promotion requires validated evidence and explicit confirmation.

---

# Historical Backtest Parity

The strategy backtest uses `run_historical_pipeline()` to reuse production components for:

```text
point-in-time feature generation
→ timeframe synchronization
→ structure / regime / orderflow context
→ neural inference
→ Brainflow
→ Layer-3 trade planning
→ Risk Firewall
→ historical execution
```

Historical entry occurs on the **next LTF bar**, not the decision bar, to avoid same-bar look-ahead. If both SL and TP are touched in the same bar, the replay resolves the ambiguity conservatively to SL.

The legacy `run_replay(realized_r)` helper is only a metrics helper and is not the strategy backtest.

---

# Runtime Modes

NeuralMT5 supports three trading modes:

| Mode | Purpose | Sends broker orders? |
|---|---|---:|
| `analysis` | Full analysis and opportunity pipeline | No |
| `paper` | Simulated execution using production planning/risk flow | No |
| `live` | Real MT5 execution behind explicit readiness gates | Yes, only when all gates pass |

Default:

```env
TRADING_MODE=analysis
```

The project never defaults to LIVE.

---

# LIVE Safety Gates

LIVE execution is intentionally difficult to enable.

The following remain false until actual host validation has been completed:

```env
LIVE_EXECUTION_ENABLED=false
LIVE_READINESS_ACKNOWLEDGED=false
LIVE_FAULT_INJECTION_PASSED=false
LIVE_SOAK_TEST_PASSED=false
```

`SYMBOLS` uses a plain comma-separated canonical format such as `SYMBOLS=XAUUSD,EURUSD`; JSON array syntax is not required. The resolver automatically maps each canonical symbol to one eligible broker symbol. Replay/playback/custom or non-openable symbols are rejected before ranking. If a broker has several legitimate variants and you need to force one, use an explicit override such as `SYMBOL_XAUUSD=XAUUSD.vx`; safety rejection still applies to manual overrides.

Additional readiness checks include:

- MT5 credential/config presence;
- terminal connectivity;
- terminal trading permission;
- account trading permission;
- model artifact availability;
- scaler artifact availability;
- broker tick clock skew;
- symbol execution specification sanity;
- valid filling-mode mapping;
- stops/freeze constraints;
- successful startup reconciliation.

See:

- [`docs/FINAL_FULL_PROJECT_AUDIT.md`](docs/FINAL_FULL_PROJECT_AUDIT.md)
- [`docs/REAL_HOST_VALIDATION.md`](docs/REAL_HOST_VALIDATION.md)

---

# Dashboard

Directory: [`dashboard/`](dashboard)

The dashboard provides observability for:

- Overview;
- Market Intelligence;
- Neural Brain;
- Opportunities;
- Open Positions;
- Trade History;
- Trade Replay;
- Performance;
- Champion / Challenger state;
- Risk Firewall;
- System Health;
- runtime events.

Versioned API endpoints include:

```text
GET  /api/v1/status
GET  /api/v1/market
GET  /api/v1/brain
GET  /api/v1/opportunities
GET  /api/v1/positions
GET  /api/v1/trades
GET  /api/v1/trades/{trade_id}/replay
GET  /api/v1/performance
GET  /api/v1/learning
GET  /api/v1/risk
GET  /api/v1/system
GET  /api/v1/system/events
POST /api/v1/commands
WS   /ws/v1/events
```

The dashboard does **not** import or directly invoke native MT5 execution. Commands are sent as runtime intents and remain subject to the normal safety gates.

Default dashboard bind:

```env
DASHBOARD_HOST=127.0.0.1
```

Remote access requires explicit opt-in, authentication, and trusted HTTPS proxy configuration.

---

# Repository Structure

```text
NeuralMT5/
├── main.py
├── train.py
├── backtest.py
├── run_dashboard.py
├── .env.example
├── requirements.txt
├── requirements-mt5.txt
├── pyproject.toml
│
├── config/                 # Typed configuration and validation
├── contracts/              # Stable cross-layer DTO/event contracts
├── layer1_market/          # Market Intelligence
├── layer2_brain/           # Local neural model, scaler, inference, Brainflow
├── layer3_execution/       # Planning, risk, sizing, execution, reconciliation
├── layer4_learning/        # Journal, datasets, backtest, walk-forward, lifecycle
├── runtime/                # Integrated orchestrator and persistent runtime state
├── dashboard/              # API, WebSocket, auth, safe commands, frontend
├── live_readiness/         # Host/readiness audit gates
├── tools/                  # Real-host preflight and soak tooling
├── storage/                # Runtime data, models, scalers, reports, logs
├── tests/                  # Regression and safety tests
└── docs/                   # Phase documentation and final audit reports
```

Runtime storage is intentionally excluded from Git except directory placeholders.

---

# Requirements

## Python

Python `3.11+` is required by `pyproject.toml`.

Core dependencies are defined in:

```text
requirements.txt
```

MT5-host-specific dependencies are defined separately in:

```text
requirements-mt5.txt
```

This keeps non-MT5 development/test environments from requiring a live terminal integration package.

---

# Installation

## 1. Clone

```bash
git clone https://github.com/syamsulmuiin/NeuralMT5.git
cd NeuralMT5
```

## 2. Create a virtual environment

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Linux/macOS development environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3. Install dependencies

Core development/runtime dependencies:

```bash
pip install -r requirements.txt
```

On the real MT5 host, also install:

```bash
pip install -r requirements-mt5.txt
```

## 4. Create local configuration

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### Linux/macOS

```bash
cp .env.example .env
```

Never commit `.env`. It may contain trading credentials and private runtime configuration.

---

# Configuration

`.env` is the single user-editable configuration source.

Main configuration groups:

```text
MT5
Symbols
Market data / timeframes / windows
Features
Network / reproducibility
Brainflow
Entry / SL / TP / RR
Risk
Execution
Session / timezone
Learning / Champion / Challenger / Drift
Database / logging
Dashboard
LIVE-readiness gates
```

Typical development configuration:

```env
TRADING_MODE=analysis
SYMBOLS=XAUUSD,EURUSD
SYMBOL_EXCLUDE_TOKENS=REPLAY,REPALY,PLAYBACK

# Optional broker-specific override. Leave blank for auto-resolution.
SYMBOL_XAUUSD=

HTF=M15
MTF=M5
LTF=M1

HTF_WINDOW=200
MTF_WINDOW=200
LTF_WINDOW=200

RISK_PER_TRADE=0.005
MIN_RR=1.50

AUTO_PROMOTION_ENABLED=false

DASHBOARD_ENABLED=true
DASHBOARD_HOST=127.0.0.1

LIVE_EXECUTION_ENABLED=false
LIVE_READINESS_ACKNOWLEDGED=false
LIVE_FAULT_INJECTION_PASSED=false
LIVE_SOAK_TEST_PASSED=false
```

See [`.env.example`](.env.example) for the complete configuration surface.

---

# Running NeuralMT5


## Train → Forward Test → Live Workflow

NeuralMT5 does not create dummy model artifacts. Before the integrated runtime can perform neural inference, train a local Challenger from MT5 historical **closed candles**:

```powershell
python train.py --diagnose
python train.py
```

`--diagnose` connects to MT5, resolves the configured symbols, inspects available HTF/MTF/LTF history, and reports exactly how many samples can be built without training. The report is saved to `storage/reports/training_data_diagnostics.json`.

The training workflow resolves configured broker symbols, downloads historical HTF/MTF/LTF candles, builds point-in-time features and synchronized sequences, creates deterministic forward labels, performs a chronological train/validation/test split with purge/embargo, fits the scaler on the **training split only**, and trains the local CNN+GRU network. Outputs are:

```text
storage/models/challenger.pt
storage/models/challenger.pt.json
storage/scalers/challenger.json
storage/reports/training_report.json
```

Training never replaces the active Champion automatically. Review `storage/reports/training_report.json`. If `passed` is `true`, promote that exact saved Challenger explicitly:

```powershell
python train.py --promote
```

Promotion does **not** retrain. It verifies the saved model/scaler hashes against the reviewed report, then installs:

```text
storage/models/champion.pt
storage/models/champion.pt.json
storage/scalers/champion.json
```

After promotion, run the historical production-pipeline backtest **before** forward testing:

```powershell
python backtest.py
```

Optional overrides:

```powershell
python backtest.py --bars 8000
python backtest.py --symbol XAUUSD
```

The backtest loads the active Champion/scaler, resolves the same broker symbols, fetches closed MT5 history, and replays the production Layer 1 → Layer 2 → Layer 3 path with next-LTF-bar execution. Reports are written to:

```text
storage/reports/backtest_report.json
storage/reports/backtest_trades.csv
```

Review the backtest report before moving to forward testing. The replay applies production planning, Risk Firewall state (including daily risk/loss and consecutive losses), execution preflight (session/cutoff/stops/freeze), next-LTF-bar execution, and conservative same-bar SL/TP resolution. It remains a candle-based historical simulation: exact intrabar path, broker latency/requotes, commissions, swaps, and real partial-fill microstructure are not reconstructed unless present in the implemented historical model. A successful command execution is **not** by itself evidence of a profitable or robust strategy.

Then run forward analysis or paper testing:

```powershell
python main.py --run
```

Recommended `.env` progression is `TRADING_MODE=analysis` first, then `TRADING_MODE=paper`. LIVE remains gated by real-host readiness and must not be enabled merely because training or backtesting succeeded. Training, Challenger promotion, and historical backtesting are blocked while `TRADING_MODE=live`.

Training controls are configured in `.env`:

```env
TRAIN_HISTORY_BARS=5000
LABEL_HORIZON_BARS=30
TRAIN_MIN_SAMPLES=300
TRAIN_MIN_BALANCED_ACCURACY=0.34
TRAIN_MIN_CLASS_SAMPLES=20
TRAIN_CLASS_WEIGHT_POWER=0.50
TRAIN_CLASSIFICATION_LOSS_WEIGHT=1.00
TRAIN_QUALITY_LOSS_WEIGHT=0.25
TRAIN_EXCURSION_LOSS_WEIGHT=0.25
BACKTEST_HISTORY_BARS=5000
BACKTEST_INITIAL_EQUITY=10000
EPOCHS=30
BATCH_SIZE=64
LEARNING_RATE=0.001
RANDOM_SEED=42
```

If training reports insufficient samples, run `python train.py --diagnose` first. The diagnostics distinguish unresolved symbols, `symbol_select` failure, missing broker history, insufficient feature history, sequence-alignment failures, and class distribution. Do not bypass the minimum-sample or validation gates with dummy artifacts.

If Challenger validation fails, `python train.py --promote` remains blocked by design. Training uses class-balanced classification weights computed from the **training split only**, with classification kept as the dominant multitask objective. `training_report.json` includes train class counts, applied class weights, predicted-class counts, and a confusion matrix so failures such as a collapsed HOLD class can be diagnosed directly. Do not lower `TRAIN_MIN_BALANCED_ACCURACY` merely to force promotion; retrain only after addressing the reported failure.


## Canonical command sequence after clone

```text
Clone / install / configure .env
        ↓
python main.py
        ↓
python train.py --diagnose
        ↓
python train.py
        ↓
review training_report.json
        ↓
python train.py --promote
        ↓
python backtest.py
        ↓
TRADING_MODE=analysis → python main.py --run
        ↓
TRADING_MODE=paper → python main.py --run
        ↓
python tools/real_host_preflight.py
        ↓
fault injection + long soak
        ↓
human LIVE-readiness review
        ↓
LIVE only after every explicit gate is satisfied
```

Each stage is a gate for the next. Do not replace failed diagnostics, training validation, backtest review, or real-host evidence with dummy artifacts or manually-forced pass flags.

## Safe configuration validation only

```bash
python main.py
```

This validates configuration and exits. It does not start the integrated MT5 runtime.

## Start integrated runtime

```bash
python main.py --run
```

## Run exactly one market cycle

```bash
python main.py --run --once
```

## Run without dashboard

```bash
python main.py --run --no-dashboard
```

The model and scaler paths configured in `.env` must exist and be compatible before the integrated runtime can start.

---

# Model & Scaler Artifacts

Default paths:

```env
MODEL_ARTIFACT_PATH=storage/models/champion.pt
SCALER_ARTIFACT_PATH=storage/scalers/champion.json
```

Runtime loading verifies compatibility between:

- feature names/order;
- feature implementation version;
- scaler version and scaler content hash;
- network artifact;
- model metadata;
- configured feature count.

The runtime does not silently create a dummy model when a required artifact is missing.

---

# Testing

Run the full regression suite:

```bash
python -m pytest
```

Current packaged baseline:

```text
112 tests passing
```

Compile audit:

```bash
python -m compileall .
```

The test suite covers, among other areas:

- broker discovery;
- symbol normalization/resolution;
- ambiguous symbol rejection;
- market-data validation;
- point-in-time feature behavior;
- timeframe synchronization;
- deterministic neural initialization/inference;
- score bounds;
- Brainflow;
- SL/TP/RR;
- broker-aware sizing;
- Risk Firewall vetoes;
- spread/slippage rejection;
- duplicate-order prevention;
- execution error handling;
- order/deal/position reconciliation;
- restart recovery;
- active-position lifecycle;
- MFE/MAE;
- chronological split;
- purge/embargo;
- historical pipeline replay;
- Champion/Challenger lifecycle;
- dashboard security/isolation;
- LIVE-readiness gates.

---

# Real MT5 Host Validation

Software tests cannot prove that a specific broker, terminal installation, account type, network, symbol specification, filling policy, or session configuration behaves exactly as expected.

NeuralMT5 therefore ships real-host validation tooling.

## Read-only preflight

```bash
python tools/real_host_preflight.py
```

The preflight checks items such as:

- MT5 terminal/account availability;
- canonical symbol resolution;
- live bid/ask availability;
- HTF/MTF/LTF history availability;
- broker execution specifications;
- trading permissions;
- model/scaler artifacts;
- readiness constraints.

It does **not** call `order_send`.

Report output:

```text
storage/reports/real_host_preflight.json
```

## Analysis / paper soak

```bash
python tools/host_soak.py --cycles 500
```

The soak tool rejects LIVE mode. It is intended for repeated `analysis`/`paper` validation on the actual MT5 host.

After preflight and soak, follow the complete fault-injection matrix in [`docs/REAL_HOST_VALIDATION.md`](docs/REAL_HOST_VALIDATION.md).

Do not set the LIVE attestations to `true` merely because unit tests pass.

---

# Persistence & Recovery

SQLite is the default local journal/database backend:

```env
DATABASE_URL=sqlite:///storage/database/neuralmt5.db
```

The runtime persists and reconciles:

- observations;
- opportunities;
- trade plans;
- order identity;
- deal identity;
- position identity;
- trade outcomes;
- model artifacts;
- promotion audit;
- system events.

Execution uses durable idempotency keys to reduce duplicate-order risk across retry/restart scenarios.

If startup reconciliation cannot establish a safe broker/journal state, new entries are paused rather than guessed.

---

# Position Lifecycle

For active positions, the integrated runtime supports:

- paper/live position maintenance before new-entry analysis;
- MFE/MAE updates;
- protective geometry checks;
- broker-side close detection;
- P/L, commission, swap and net P/L accounting;
- realized R;
- exit reason persistence;
- deterministic paper SL/TP handling;
- configured intraday force-flat;
- fail-closed partial force-flat behavior;
- restart reconciliation.

---

# Reproducibility & Auditability

Historical decisions are designed to carry version metadata such as:

```text
strategy_version
feature_version
network_version
dataset_version
scaler_version
config_hash
weights_hash
dataset_hash
random_seed
```

Deterministic seeds are applied where supported. Model/scaler/data/config compatibility is treated as part of the decision audit trail, not optional metadata.

---

# Security

Important defaults and constraints:

- `.env` is ignored by Git;
- dashboard binds to localhost by default;
- dashboard secrets are not exposed as normal API payloads;
- remote dashboard access is opt-in;
- remote access requires authentication and trusted HTTPS proxy configuration;
- dashboard code cannot directly execute MT5 orders;
- LIVE requires multiple explicit gates;
- Champion promotion is not automatic by default;
- existing position safety monitoring must continue even when new entries are paused.

---

# Documentation

The active documentation set is intentionally small. Development-history documents were removed because Git already preserves that history.

| Document | Purpose |
|---|---|
| [`README.md`](README.md) | Primary project documentation, architecture, setup, operation, and safety model |
| [`docs/FINAL_FULL_PROJECT_AUDIT.md`](docs/FINAL_FULL_PROJECT_AUDIT.md) | Current software audit and readiness verdict |
| [`docs/REAL_HOST_VALIDATION.md`](docs/REAL_HOST_VALIDATION.md) | Required real MT5 host/broker validation procedure before LIVE consideration |

These documents describe the **current repository state** rather than historical development phases.

---

# Current Limitations

The current software baseline is intentionally conservative.

The repository should **not** be represented as production LIVE-ready until the documented real-host validation has been completed on the actual MT5 environment, including:

- disconnect/reconnect with active positions;
- terminal restart with active positions;
- broker partial fills where available;
- account-specific netting/hedging identity behavior;
- real filling-mode acceptance;
- real stops/freeze behavior;
- session/timezone verification for the selected broker;
- long-duration analysis/paper soak;
- restart/reconciliation evidence;
- fault injection around execution boundaries.

These are environmental validations, not conditions that should be faked or auto-attested by source code.

---

# Development Philosophy

NeuralMT5 intentionally prefers:

```text
HOLD instead of weak edge
REJECT instead of unsafe execution
FAIL CLOSED instead of guessing state
VALIDATED CHALLENGER instead of automatic self-modification
BROKER FACTS instead of hardcoded assumptions
POINT-IN-TIME DATA instead of optimistic backtests
AUDITABLE STATE instead of silent mutation
```

The goal is not maximum trade frequency or a promised win rate. The goal is a local, explainable and reproducible trading system that learns from its own validated data while deterministic risk controls remain the final authority over capital.

---

# Disclaimer

NeuralMT5 is software for research, engineering, testing, and controlled trading-system development. Trading leveraged financial instruments involves substantial risk. No code, model, backtest result, dashboard metric, or validation status guarantees profitability or prevents losses.

Use paper/analysis modes first, validate the system on the actual broker/terminal environment, and independently verify all risk settings before considering LIVE execution.
