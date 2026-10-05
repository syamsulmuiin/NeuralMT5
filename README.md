Anda adalah **Senior Quantitative Trading Engineer, Python/MetaTrader 5 Engineer, Neural Network Engineer, Market Microstructure Engineer, Risk Engineer, Data Engineer, dan Trading System Architect**.

Bangun dari nol sebuah sistem **Python + MetaTrader 5 (MT5)** untuk **scalping/intraday** yang production-oriented, modular, broker-agnostic, auditable, reproducible, restart-safe, explainable, memiliki local self-trained neural network, controlled self-improvement, serta dashboard real-time lengkap.

Sistem harus menangani seluruh lifecycle:

**MT5 → Broker/Symbol Discovery → Data → Pre-Analysis → Multi-Timeframe Analysis → Orderflow → Neural Brain → Brainflow → BUY/SELL/HOLD → Opportunity → Entry/SL/TP/RR → Risk Validation → Execution → Position Monitoring → Exit → Reconciliation → Journal → Performance → Training → Validation → Champion/Challenger → Controlled Improvement → Dashboard**

Target bukan memperbanyak transaksi atau mengejar win rate.

Prioritas absolut:

1. Capital preservation
2. Data integrity
3. Risk control
4. Execution correctness
5. Positive expectancy
6. Robustness
7. Neural learning
8. Trade frequency

Jika tidak ada edge yang cukup jelas:

**HOLD.**

---

# 1. FUNDAMENTAL SYSTEM CONTRACT

Strategi adalah **scalping/intraday**.

Posisi normalnya harus entry dan close pada hari/sesi trading yang sama.

Sistem harus:

- menentukan BUY / SELL / HOLD;
- memberikan Entry;
- selalu memberikan SL untuk trade valid;
- memberikan TP;
- menghitung RR;
- menghitung lot berdasarkan risiko;
- memonitor posisi;
- mengetahui hasil SL/TP/exit lainnya;
- melakukan reconciliation dengan MT5;
- menyimpan seluruh observation;
- membuat rekap;
- belajar dari data lama dan data baru;
- meningkatkan sistem hanya setelah improvement tervalidasi.

Jangan menjanjikan profit.

Optimasi diarahkan pada:

**positive expectancy + controlled drawdown + stability + robustness + execution quality.**

---

# 2. ZERO EXTERNAL DECISION MODEL

Tidak boleh menggunakan model/sinyal eksternal untuk mengambil keputusan trading.

Dilarang menggunakan:

- OpenAI;
- Gemini;
- Claude;
- external LLM;
- pretrained trading model;
- third-party AI signal;
- external BUY/SELL signal;
- copy trading;
- external decision API.

Tidak ada model eksternal yang boleh menentukan:

- BUY;
- SELL;
- HOLD;
- Entry;
- SL;
- TP;
- lot;
- risk;
- exit.

Neural network harus:

1. dibuat sendiri;
2. initial weights dibuat sendiri;
3. dilatih sendiri;
4. menggunakan dataset sistem sendiri;
5. disimpan lokal;
6. diinference lokal.

Framework seperti:

- PyTorch;
- TensorFlow;
- JAX;
- NumPy

boleh digunakan hanya sebagai mathematical/training framework.

**Jangan menggunakan pretrained weights.**

Rekomendasi baseline: **PyTorch**, kecuali benchmark project menunjukkan pilihan lain lebih sederhana/tepat.

---

# 3. REPRODUCIBILITY

Dengan:

- input sama;
- model weights sama;
- scaler sama;
- config sama;
- feature version sama;

live inference harus menghasilkan output yang sama sejauh framework/hardware memungkinkan.

Simpan:

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

Set deterministic/random seed yang diperlukan.

Setiap keputusan historis harus dapat diaudit.

---

# 4. GLOBAL SCORING CONTRACT

Semua nilai yang secara semantik merupakan:

- score;
- probability;
- confidence;
- strength;
- quality;
- fitness;

wajib menggunakan:

```text
0.0 <= value <= 1.0
```

Contoh:

```text
HTF_strength       = 0.82
MTF_quality        = 0.76
LTF_quality        = 0.91

structure_score    = 0.84
orderflow_score    = 0.73
regime_fitness     = 0.88
momentum_score     = 0.79

buy_score          = 0.86
sell_score         = 0.09
hold_score         = 0.05

brainflow_score    = 0.84
confidence         = 0.83
risk_quality       = 0.91
```

Jangan mencampur score `0–100` dengan `0–1`.

Harga, spread, ATR, lot, P/L, RR, MFE, MAE dan physical values lainnya tetap memakai unit aslinya.

Direction tetap categorical:

```text
BUY
SELL
HOLD
```

Jangan menggunakan `0=SELL, 1=BUY` sebagai score.

---

# 5. FOUR-LAYER ARCHITECTURE

Gunakan tepat empat domain trading utama:

```text
                         MT5
                          │
                          ▼
              ┌───────────────────────┐
              │       LAYER 1         │
              │ MARKET INTELLIGENCE   │
              │                       │
              │ Broker Discovery      │
              │ Generic Symbols       │
              │ Data Validation       │
              │ HTF / MTF / LTF       │
              │ Features              │
              │ Structure / Regime    │
              │ Orderflow             │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │       LAYER 2         │
              │ LOCAL NEURAL BRAIN    │
              │                       │
              │ HTF Encoder           │
              │ MTF Encoder           │
              │ LTF Encoder           │
              │ Fusion                │
              │ Brainflow             │
              │ BUY / SELL / HOLD     │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │       LAYER 3         │
              │ RISK & EXECUTION      │
              │                       │
              │ Trade Planner         │
              │ Entry                 │
              │ Deterministic SL/TP   │
              │ RR                    │
              │ Position Size         │
              │ Risk Firewall         │
              │ Execute / Monitor     │
              │ Reconciliation        │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │       LAYER 4         │
              │ MEMORY & EVOLUTION    │
              │                       │
              │ Journal               │
              │ Dataset               │
              │ Training              │
              │ Backtest              │
              │ Walk Forward          │
              │ Challenger            │
              │ Shadow                │
              │ Drift                 │
              └───────────┬───────────┘
                          │
                 VALIDATED WEIGHTS
                          │
                          └──────────────→ LAYER 2
```

Layer 2 menentukan apakah terdapat edge.

Layer 3 menentukan apakah edge tersebut aman dan executable.

**Layer 3 mempunyai VETO POWER absolut.**

Layer 4 tidak boleh melewati hard safety Layer 3.

Dashboard bukan Layer 5.

---

# 6. LAYER 1 — MARKET INTELLIGENCE

Pipeline:

```text
MT5
↓
Connection
↓
Broker Discovery
↓
Generic Symbol Resolver
↓
Market Data
↓
Data Validation
↓
Point-in-Time Features
↓
Structure
↓
Regime
↓
Orderflow
↓
HTF/MTF/LTF Sequences
↓
Normalized Neural Input
```

## 6.1 GENERIC BROKER SUPPORT

Jangan hardcode broker tertentu.

Discover otomatis:

```text
digits
point
tick_size
tick_value
contract_size
volume_min
volume_max
volume_step
stops_level
freeze_level
trade_mode
filling_mode
execution_mode
spread
margin
session information
```

Seluruh calculation harus mengikuti actual broker specification.

---

# 7. GENERIC SYMBOL RESOLVER

Broker dapat menggunakan:

```text
XAUUSD
XAUUSDm
XAUUSD.m
XAUUSD.vx
XAUUSDpro
GOLD
GOLDm
```

User cukup menentukan canonical symbol:

```text
XAUUSD
EURUSD
GBPUSD
USDJPY
...
```

Python harus mencari actual broker symbol.

Gunakan kombinasi:

- normalized symbol;
- prefix/suffix;
- description;
- path/category;
- currency_base;
- currency_profit;
- currency_margin;
- trade mode;
- digits;
- point;
- contract size.

Jangan hanya menggunakan substring atau `startswith()`.

Output:

```text
canonical_symbol
broker_symbol
resolution_confidence
reason
```

`resolution_confidence` menggunakan `0–1`.

Jika ambigu:

**NO TRADE.**

Support manual `.env` override:

```env
SYMBOL_XAUUSD=
SYMBOL_EURUSD=
```

Kosong berarti auto-resolve.

---

# 8. DATA QUALITY

Sebelum analisa periksa:

- MT5 connection;
- market state;
- stale tick;
- incomplete candle;
- missing candle;
- duplicate candle;
- malformed OHLC;
- insufficient history;
- abnormal spread;
- invalid timestamp;
- timeframe alignment.

Jika data invalid:

```text
HOLD
```

Neural network tidak boleh menerima data yang diketahui rusak.

---

# 9. POINT-IN-TIME CONTRACT

Feature pada waktu `T` hanya boleh menggunakan informasi yang tersedia pada `T`.

Dilarang:

- future candle;
- future swing information;
- centered rolling calculation yang membaca masa depan;
- future normalization;
- target leakage;
- scaler leakage.

Backtest, training, paper dan live harus mengikuti prinsip yang sama.

---

# 10. GENERIC MULTI-TIMEFRAME

Timeframe tidak boleh terkunci pada kombinasi tertentu.

Semua timeframe configurable.

Contoh:

```env
HTF=M15
MTF=M5
LTF=M1

HTF_WINDOW=200
MTF_WINDOW=200
LTF_WINDOW=200
```

Konsep:

```text
HTF → CONTEXT / BIAS
MTF → CONDITION / SETUP
LTF → PRECISE TIMING
```

Support timeframe MT5 relevan:

```text
M1
M2
M3
M4
M5
M6
M10
M12
M15
M20
M30
H1
H2
H3
H4
H6
H8
H12
D1
```

sesuai kemampuan actual MT5 Python API.

Jangan hardcode M15/M5/M1 ke strategy implementation.

---

# 11. NEURAL INPUT SHAPE

Jangan menganggap `200×200` selalu benar.

Gunakan:

```text
sequence_length × feature_count
```

Contoh:

```text
200 candles × 40 features
= 200 × 40
```

Window dan feature count configurable/versioned.

---

# 12. FEATURE ENGINEERING

Feature dapat mencakup:

### RAW

- OHLC;
- returns;
- log returns;
- candle range;
- body;
- wick;
- tick volume;
- spread.

### STRUCTURE

- HH;
- HL;
- LH;
- LL;
- swings;
- BOS;
- CHoCH;
- distance to structure;
- support/resistance;
- supply/demand;
- liquidity sweep;
- breakout;
- retest;
- rejection;
- displacement;
- compression/expansion.

### VOLATILITY

- ATR;
- realized volatility;
- range expansion;
- compression.

### MOMENTUM

- rate of change;
- normalized momentum;
- velocity;
- acceleration.

Jangan melakukan indicator stacking tanpa evidence bahwa feature tersebut membantu out-of-sample performance.

---

# 13. ORDERFLOW

Gunakan data yang benar-benar tersedia.

Jika broker hanya memberikan tick volume, jangan menyebutnya centralized exchange volume.

Orderflow/proxy dapat menggunakan:

```text
tick activity
bid/ask movement
spread dynamics
price velocity
acceleration
tick-volume anomaly
rejection
absorption proxy
imbalance proxy
```

Jika Market Depth tersedia dan valid, gunakan adapter terpisah.

Bedakan:

```text
REAL MARKET DATA
```

dengan:

```text
DERIVED PROXY
```

---

# 14. MARKET REGIME

Deteksi kondisi seperti:

```text
TREND_UP
TREND_DOWN
RANGE
BREAKOUT
COMPRESSION
EXPANSION
HIGH_VOLATILITY
LOW_VOLATILITY
CHAOTIC
```

Regime menjadi feature/context.

Jangan menggunakan setup secara buta pada semua kondisi pasar.

---

# 15. NORMALIZATION

Scaler hanya boleh di-fit menggunakan training data.

Validation/test/paper/live menggunakan scaler training tersebut.

Dilarang:

```text
fit entire dataset
↓
split dataset
```

Simpan scaler sebagai versioned artifact.

---

# 16. LAYER 2 — LOCAL NEURAL BRAIN

Gunakan multi-timeframe multi-branch architecture:

```text
HTF Sequence → HTF Encoder ─┐
                            │
MTF Sequence → MTF Encoder ─┼→ FUSION → NEURAL BRAIN
                            │
LTF Sequence → LTF Encoder ─┘
```

Jangan sekadar mencampur seluruh timeframe mentah menjadi satu sequence.

Mulai dari architecture yang relatif sederhana.

Candidate baseline:

```text
Temporal 1D CNN
+
GRU/LSTM
+
small dense fusion network
```

Tetapi architecture final harus dipilih berdasarkan benchmark out-of-sample, bukan karena paling kompleks.

---

# 17. MULTI-TASK NEURAL OUTPUT

Jangan hanya train:

```text
WIN / LOSS
```

Network sebaiknya belajar beberapa target:

```text
BUY probability
SELL probability
HOLD probability

setup quality
direction confidence

expected favorable excursion
expected adverse excursion
```

Quality/probability outputs harus `0–1`.

Continuous targets boleh dinormalisasi untuk training sambil menyimpan nilai aslinya untuk evaluation.

---

# 18. BUY / SELL / HOLD

Output utama:

```text
buy_score
sell_score
hold_score
```

dengan kira-kira:

```text
buy_score + sell_score + hold_score = 1.0
```

Jangan hanya menggunakan `argmax`.

Gunakan:

```env
MIN_DIRECTION_SCORE=
MIN_DIRECTION_MARGIN=
MIN_CONFIDENCE=
MIN_BRAINFLOW_SCORE=
```

Contoh:

```text
BUY  = 0.52
SELL = 0.44
HOLD = 0.04
```

Walaupun BUY terbesar, BUY dan SELL terlalu dekat.

Hasil:

```text
HOLD
```

Ambiguous prediction tidak boleh dipaksa menjadi trade.

---

# 19. BRAINFLOW

Brainflow adalah evidence aggregation layer.

Contoh:

```text
brainflow =
    HTF_strength      × W_HTF
  + MTF_quality       × W_MTF
  + LTF_quality       × W_LTF
  + structure_score   × W_STRUCTURE
  + orderflow_score   × W_ORDERFLOW
  + regime_fitness    × W_REGIME
  + momentum_score    × W_MOMENTUM
  + neural_confidence × W_NEURAL
```

Constraint:

```text
Σ weights = 1.0
```

Maka Brainflow tetap `0–1`.

Bobot configurable melalui `.env`.

Layer 4 boleh menghasilkan challenger weights, tetapi tidak boleh langsung mengubah live weights tanpa validation.

---

# 20. LAYER 3 — DETERMINISTIC TRADE PLANNING

Neural network memberikan:

```text
direction
probability
quality
confidence
```

Tetapi network tidak boleh bebas menentukan harga absolut SL/TP.

Pipeline:

```text
Neural Opportunity
↓
Current Market Revalidation
↓
Entry
↓
SL
↓
TP
↓
RR
↓
Risk
↓
Position Size
↓
Execution
```

---

# 21. ENTRY

Entry ditentukan menggunakan actual current market state.

Jangan mengeksekusi harga lama secara buta.

Sesaat sebelum execution, refresh tick dan revalidate opportunity.

---

# 22. STOP LOSS

**NO SL = NO TRADE.**

SL final deterministic.

Pertimbangkan:

```text
market structure
swing invalidation
volatility
ATR/noise
liquidity
spread
broker stops level
tick size
```

Jika SL terlalu sempit:

```text
REJECT
```

Jika terlalu jauh sehingga risk/RR buruk:

```text
REJECT
```

Jangan memasang SL setelah posisi dibuka sebagai normal workflow.

---

# 23. TAKE PROFIT

TP dapat mempertimbangkan:

```text
market structure
next liquidity
support/resistance
expected move
volatility
session range
```

Hitung:

```text
risk   = abs(entry - SL)
reward = abs(TP - entry)

RR = reward / risk
```

Jika:

```text
RR < MIN_RR
```

maka:

```text
REJECT
```

Jangan menggeser SL secara tidak logis untuk mempercantik RR.

---

# 24. POSITION SIZE

Lot berdasarkan risk.

Gunakan:

```text
account equity
risk %
entry
SL
tick size
tick value
contract specification
```

Normalize berdasarkan:

```text
volume_min
volume_max
volume_step
```

Jika minimum lot broker membuat actual risk terlalu besar:

```text
REJECT
```

---

# 25. RISK FIREWALL

Hard limits configurable:

```env
RISK_PER_TRADE=
MAX_DAILY_RISK=
MAX_DAILY_LOSS=
MAX_CONSECUTIVE_LOSSES=
MAX_OPEN_POSITIONS=
MAX_TOTAL_EXPOSURE=
MAX_CORRELATED_EXPOSURE=
MAX_SPREAD=
MAX_SLIPPAGE=
```

Risk Engine memiliki **ABSOLUTE VETO POWER**.

Contoh:

```text
NEURAL:
BUY 0.94

BRAINFLOW:
0.91

RISK:
REJECTED

REASON:
Daily loss limit reached
```

Final:

```text
NO TRADE
```

Neural network tidak boleh menonaktifkan risk firewall.

---

# 26. EXECUTION PREFLIGHT

Sebelum `order_send()` validasi ulang:

```text
MT5 connection
symbol
fresh tick
market status
spread
entry
SL
TP
RR
lot
margin
slippage
session
daily risk
existing positions
correlated exposure
duplicate signal
```

---

# 27. IDEMPOTENCY / DUPLICATE PROTECTION

Setiap opportunity memiliki:

```text
signal_id
trade_intent_id
```

Network reconnect/retry tidak boleh menghasilkan duplicate order.

---

# 28. EXECUTION ERROR HANDLING

Tangani:

```text
accepted
rejected
requote
invalid stops
partial fill
market closed
insufficient margin
timeout
connection loss
```

Jangan menyembunyikan critical MT5 errors.

---

# 29. POSITION MONITOR

Monitor:

```text
current price
floating P/L
SL
TP
MFE
MAE
spread
holding duration
market state
```

Optional/configurable:

```text
break-even
trailing stop
partial close
structure exit
time stop
```

Jangan aktifkan hidden behavior.

---

# 30. INTRADAY CONTROL

Gunakan:

```env
TRADING_SESSION_START=
TRADING_SESSION_END=
NO_NEW_ENTRY_AFTER=
FORCE_FLAT_TIME=
```

Posisi scalping tidak boleh berubah menjadi overnight trade secara tidak sengaja.

---

# 31. RECONCILIATION

Jangan menganggap posisi yang hilang berarti otomatis TP/SL.

Periksa MT5 deals/history.

Classify:

```text
TP
SL
MANUAL_CLOSE
STRATEGY_EXIT
TIME_EXIT
PARTIAL
BROKER_CLOSE
ERROR
```

Simpan:

```text
planned_entry
actual_entry
SL
TP
actual_exit
gross_PL
commission
swap
net_PL
realized_R
MFE
MAE
slippage
duration
```

---

# 32. RESTART RECOVERY

Setelah restart:

```text
Connect MT5
↓
Load Database
↓
Load Champion
↓
Verify Weights Hash
↓
Load Correct Scaler
↓
Broker Discovery
↓
Resolve Symbols
↓
Find Open Positions
↓
Find Pending Orders
↓
Reconcile History
↓
Restore State
↓
Resume Monitoring
```

Jangan duplicate entry setelah restart.

---

# 33. LAYER 4 — MEMORY & EVOLUTION

Layer 4 merupakan self-learning lokal.

Pipeline:

```text
Historical Market Data
+
New Observations
+
Completed Trades
        ↓
Point-in-Time Dataset
        ↓
Training
        ↓
Challenger
        ↓
Backtest
        ↓
Walk-Forward
        ↓
Out-of-Sample
        ↓
Robustness Test
        ↓
Shadow/Paper
        ↓
Champion Comparison
        ↓
Controlled Promotion
```

Training tidak boleh mengubah active Champion yang sedang dipakai secara langsung.

---

# 34. OBSERVATION DATASET

Jangan hanya menyimpan executed trades.

Simpan juga:

```text
BUY candidates
SELL candidates
HOLD
Risk-rejected candidates
```

beserta kondisi pasar dan future outcome yang dibuat secara point-in-time untuk training/evaluation.

Hal ini mengurangi selection bias dari strategi sebelumnya.

---

# 35. DATASET CONTENT

Observation dapat berisi:

```text
timestamp
canonical symbol
broker symbol

HTF sequence
MTF sequence
LTF sequence

regime
structure
orderflow
volatility
spread

neural outputs
brainflow
decision

future excursion
MFE
MAE
future return
outcome
realized R jika executed
```

---

# 36. TIME-SERIES TRAINING

Jangan menggunakan random shuffle split sebagai metode utama.

Gunakan chronological:

```text
TRAIN
↓
VALIDATION
↓
TEST
```

dan walk-forward:

```text
Train A → Test B

Train A+B → Test C

Train A+B+C → Test D
```

Jika labels menggunakan future horizon, gunakan purge/embargo jika diperlukan agar tidak terjadi overlapping leakage.

---

# 37. CLASS IMBALANCE

Audit distribusi:

```text
BUY
SELL
HOLD
```

Jangan membiarkan network belajar selalu HOLD hanya karena class imbalance.

Gunakan class weighting/sampling/loss adjustment jika memang diperlukan dan terbukti membantu out-of-sample.

---

# 38. CHAMPION VS CHALLENGER

Live network:

```text
CHAMPION
```

Training menghasilkan:

```text
CHALLENGER
```

Challenger harus melewati:

```text
training
validation
historical backtest
walk-forward
out-of-sample
robustness
shadow/paper
Champion comparison
```

Bandingkan:

```text
expectancy
profit factor
total R
average R
drawdown
stability
calibration
trade count
symbol robustness
regime robustness
session robustness
```

Training accuracy yang lebih tinggi tidak otomatis berarti Challenger lebih baik.

Default:

```env
AUTO_PROMOTION_ENABLED=false
```

---

# 39. SHADOW MODE

Challenger melakukan inference pada data market yang sama dengan Champion tetapi:

**TIDAK BOLEH MENGIRIM ORDER.**

Simpan perbandingan:

```text
Champion decision
Challenger decision
actual future outcome
```

untuk forward validation.

---

# 40. ROLLING RETRAIN

Retraining dapat dipicu berdasarkan:

```text
N new observations
N trading days
performance drift
manual command
```

Jangan retrain setelah setiap loss.

---

# 41. CATASTROPHIC FORGETTING

Jangan train hanya menggunakan market terbaru.

Pertahankan representative historical observations dari berbagai regime.

History strategy harus configurable.

---

# 42. DRIFT DETECTION

Monitor:

```text
feature distribution
volatility
spread
regime distribution
prediction distribution
confidence calibration
expectancy
MFE
MAE
```

Status:

```text
NORMAL
WARNING
DEGRADED
SUSPENDED
```

Severe degradation dapat menyebabkan system berpindah ke analysis/paper sesuai configuration.

Jangan menaikkan risk untuk mengejar degradation.

---

# 43. CONFIDENCE CALIBRATION

Jangan menganggap softmax `0.90` otomatis berarti probabilitas keberhasilan 90%.

Uji calibration menggunakan validation/out-of-sample data.

Jika diperlukan, calibration hanya boleh dilatih menggunakan data yang sesuai tanpa leakage.

---

# 44. JOURNAL DATABASE

Gunakan SQLite sebagai baseline.

Simpan minimal:

```text
symbols
market_observations
market_snapshots
features
neural_predictions
opportunities
signals
orders
positions
deals
trades
MFE_MAE
datasets
training_runs
network_versions
scaler_versions
validation_results
Champion_history
Challenger_history
daily_metrics
config_versions
errors
```

Setiap keputusan harus dapat direkonstruksi.

---

# 45. DASHBOARD — OBSERVABILITY & CONTROL PLANE

Tambahkan **web dashboard lokal**.

Dashboard bukan Layer 5.

Dashboard tidak mengambil keputusan trading.

Architecture:

```text
4-LAYER TRADING ENGINE
        │
        ├── Runtime State
        ├── Event Bus
        └── Journal Database
                │
                ▼
          Dashboard API
                │
        ┌───────┴────────┐
        ▼                ▼
      REST            WebSocket
        │                │
        └───────┬────────┘
                ▼
          WEB DASHBOARD
```

Rekomendasi backend:

```text
FastAPI
REST
WebSocket
```

Frontend harus ringan dan maintainable.

---

# 46. DASHBOARD ISOLATION

Dashboard harus dipisahkan dari critical trading loop.

Jika:

```text
dashboard crash
browser closed
frontend error
WebSocket disconnect
dashboard API unavailable
```

trading engine tetap berjalan.

Dashboard failure tidak boleh:

```text
menghentikan SL monitoring
menghentikan position monitoring
menggandakan order
mengubah neural weights
menghentikan reconciliation
```

Prioritas runtime:

```text
1. Position safety
2. Execution
3. Market processing
4. Neural inference
5. Persistence
6. Dashboard
```

---

# 47. DASHBOARD — OVERVIEW

Tampilkan:

```text
SYSTEM

MT5
BROKER
ACCOUNT
MARKET
TRADING MODE

LAYER 1 STATUS
LAYER 2 STATUS
LAYER 3 STATUS
LAYER 4 STATUS

CHAMPION
CHALLENGER
DRIFT STATUS

TODAY

Opportunities
BUY
SELL
HOLD

Executed
Rejected

Wins
Losses

Net P/L
Realized R
Profit Factor
Expectancy
Drawdown
```

---

# 48. DASHBOARD — LIVE MARKET

Tampilkan semua symbol:

```text
SYMBOL
BROKER SYMBOL
BID
ASK
SPREAD
REGIME
DATA QUALITY
STATUS
```

Detail:

```text
Canonical Symbol
Broker Symbol
Resolution Confidence

HTF
MTF
LTF

ATR
Volatility
Regime
Spread
Last Tick
Last Candle
```

---

# 49. DASHBOARD — NEURAL BRAIN

Tampilkan:

```text
NEURAL BRAIN

Champion:
Feature Version:
Scaler:
Weights Hash:

HTF Window:
MTF Window:
LTF Window:

HTF Strength       0.xx
MTF Quality        0.xx
LTF Quality        0.xx

Structure          0.xx
Orderflow          0.xx
Regime Fitness     0.xx
Momentum           0.xx

BUY                0.xx
SELL               0.xx
HOLD               0.xx

Brainflow          0.xx
Confidence         0.xx

FINAL DECISION:
BUY / SELL / HOLD
```

Semua score `0–1`.

---

# 50. BRAINFLOW CONTRIBUTION VIEW

Tampilkan:

```text
COMPONENT      SCORE     WEIGHT     CONTRIBUTION

HTF            0.xx      0.xx       0.xxx
MTF            0.xx      0.xx       0.xxx
LTF            0.xx      0.xx       0.xxx
Structure      0.xx      0.xx       0.xxx
Orderflow      0.xx      0.xx       0.xxx
Regime         0.xx      0.xx       0.xxx
Neural         0.xx      0.xx       0.xxx
```

Visual bar boleh digunakan tetapi underlying values tetap `0–1`.

---

# 51. NETWORK INFORMATION

Dashboard menampilkan:

```text
Champion Version
Architecture
Parameter Count
Input Shape
Feature Count

HTF Window
MTF Window
LTF Window

Dataset Version
Training Period
Validation Period
Test Period
Training Date

Random Seed
Weights Hash
Scaler Hash
```

---

# 52. DASHBOARD — OPPORTUNITIES

Tampilkan bukan hanya executed trade.

```text
TIME
SYMBOL
DECISION
BUY
SELL
HOLD
BRAIN
CONF
ENTRY
SL
TP
RR
STATUS
```

Status:

```text
HOLD
EXECUTED
REJECTED
```

Jika REJECTED, tampilkan alasan:

```text
RR insufficient
spread too high
invalid SL
daily risk reached
margin insufficient
duplicate signal
```

---

# 53. DASHBOARD — LIVE POSITIONS

Tampilkan:

```text
Symbol
Direction

Entry
Current
SL
TP

Planned RR
Risk

P/L
Realized/Floating R

MFE
MAE
Duration

Brainflow
Original Confidence
Champion Version
```

Tampilkan visual jarak current price terhadap Entry/SL/TP.

---

# 54. DASHBOARD — TRADE HISTORY

Tabel:

```text
TIME
SYMBOL
DIRECTION
ENTRY
EXIT
SL
TP
RR
RESULT
P/L
R
MFE
MAE
DURATION
BRAIN
CONFIDENCE
CHAMPION
```

Filter:

```text
date
symbol
direction
win/loss
regime
session
Champion version
```

---

# 55. TRADE REPLAY

Setiap trade/opportunity harus dapat dibuka kembali.

Gunakan snapshot asli saat keputusan dibuat.

Tampilkan:

```text
HTF state
MTF state
LTF state

features
structure
regime
orderflow

BUY
SELL
HOLD

Brainflow
Confidence

Entry
SL
TP
RR

Risk decision
Execution result

MFE
MAE
Final outcome
```

Jangan merekonstruksi keputusan lama menggunakan data sekarang jika original snapshot tersedia.

---

# 56. DASHBOARD — PERFORMANCE

Tampilkan:

```text
Net P/L
Total R
Average R
Win Rate
Profit Factor
Expectancy
Max Drawdown

Average Win
Average Loss
Average RR
Average MFE
Average MAE
Average Duration
```

Charts:

```text
equity curve
cumulative R
drawdown
rolling expectancy
rolling win rate
MFE vs MAE
```

Breakdown:

```text
symbol
regime
session
direction
volatility
confidence bucket
Brainflow bucket
Champion version
```

---

# 57. DASHBOARD — LEARNING

Tampilkan:

```text
CURRENT CHAMPION

Version
Dataset
Training Date
OOS Expectancy
OOS Profit Factor
OOS Drawdown
Calibration

CURRENT CHALLENGER

Version
Status
Training progress
Validation
Walk-forward
OOS
Shadow
```

Comparison:

```text
METRIC           CHAMPION     CHALLENGER

Expectancy
Profit Factor
Average R
Drawdown
Calibration
Trade Count
```

---

# 58. TRAINING MONITOR

Ketika training berlangsung:

```text
Dataset Version
Samples

Train Samples
Validation Samples
Test Samples

Epoch
Training Loss
Validation Loss

Best Epoch
Early Stop
Elapsed Time
```

Training harus menggunakan worker/process terpisah jika diperlukan agar tidak memblokir trading loop.

---

# 59. CHAMPION HISTORY

Simpan:

```text
v1 → v2 → v3 → ...
```

Jangan menghapus previous Champion.

Simpan:

```text
promotion date
validation metrics
previous version
new version
reason
rollback target
```

---

# 60. DASHBOARD — ORDERFLOW

Tampilkan:

```text
Tick Activity
Bid/Ask Movement
Spread Dynamics
Velocity
Acceleration
Volume Anomaly
Rejection
Absorption Proxy
Imbalance Proxy
```

Bedakan real data dan derived proxy.

---

# 61. DASHBOARD — RISK

Tampilkan:

```text
Balance
Equity
Free Margin

Daily Risk Used
Daily Risk Limit

Daily P/L
Daily Loss Limit

Open Positions
Max Positions

Total Exposure
Correlated Exposure

Consecutive Losses
Maximum Allowed
```

Risk Firewall:

```text
✓ SL
✓ RR
✓ Spread
✓ Slippage
✓ Margin
✓ Daily Risk
✓ Exposure
✓ Position Limit

FINAL:
ALLOWED / REJECTED
```

---

# 62. DASHBOARD — SYSTEM HEALTH

Tampilkan:

```text
MT5
Database
Market Data
Neural Engine
Champion
Scaler
Execution Engine
Position Monitor
Learning Worker
Dashboard API

CPU
RAM
Disk

Last Tick
Last Analysis
Last Inference
Last DB Write
Last Order
Last Reconciliation
```

Tampilkan warnings/errors terbaru.

---

# 63. DASHBOARD CONFIGURATION

Dashboard boleh membaca active configuration.

Secret tidak boleh ditampilkan.

Default:

```text
READ ONLY
```

Jika config editing kemudian diimplementasikan, wajib:

```text
explicit save
validation
audit log
restart-required indicator
```

Jangan mengubah `.env` diam-diam.

---

# 64. SAFE MANUAL CONTROLS

Dashboard boleh menyediakan:

```text
PAUSE NEW ENTRY
RESUME NEW ENTRY

ANALYSIS MODE
PAPER MODE

EMERGENCY STOP NEW ENTRY
```

Emergency stop menghentikan entry baru tetapi:

**existing position safety monitoring tetap berjalan.**

Perubahan ke:

```text
LIVE MODE
```

harus membutuhkan explicit confirmation.

---

# 65. CHALLENGER PROMOTION

Karena default:

```env
AUTO_PROMOTION_ENABLED=false
```

dashboard dapat menampilkan:

```text
CHALLENGER READY
```

User dapat melihat validation report.

Promotion membutuhkan explicit confirmation.

Simpan audit:

```text
timestamp
old Champion
new Champion
validation
action
```

---

# 66. EVENT BUS

Implementasikan event stream internal:

```text
MARKET_UPDATE
ANALYSIS_COMPLETE
NEURAL_INFERENCE

OPPORTUNITY
TRADE_REJECTED

ORDER_SENT
ORDER_FILLED

POSITION_UPDATE
POSITION_CLOSED
RECONCILIATION_COMPLETE

TRAINING_STARTED
TRAINING_PROGRESS
TRAINING_COMPLETED

CHALLENGER_READY
MODEL_PROMOTED

DRIFT_WARNING

SYSTEM_WARNING
SYSTEM_ERROR
```

Dashboard menerima event via WebSocket.

Jangan polling database setiap detik jika event stream tersedia.

---

# 67. API CONTRACT

Gunakan versioned API:

```text
/api/v1/status
/api/v1/market
/api/v1/brain
/api/v1/opportunities
/api/v1/positions
/api/v1/trades
/api/v1/performance
/api/v1/learning
/api/v1/risk
/api/v1/system
```

WebSocket:

```text
/ws/v1/events
```

Frontend tidak boleh mengakses internal Python objects secara langsung.

---

# 68. DASHBOARD SECURITY

Default:

```text
127.0.0.1
```

Jangan expose dashboard ke internet secara default.

Jika remote access diaktifkan:

```text
authentication
TLS/reverse proxy
session security
rate limiting
command authorization
```

MT5 password tidak boleh masuk browser/localStorage.

Dashboard responsive untuk desktop/tablet/mobile.

---

# 69. .ENV — SINGLE CONFIGURATION SOURCE

Semua parameter yang dapat berubah harus berada di `.env`.

Kelompokkan:

```text
MT5

SYMBOLS

DATA
TIMEFRAMES
WINDOWS

FEATURES
NORMALIZATION

NETWORK
TRAINING

BRAINFLOW

ENTRY
SL
TP
RR

RISK
EXECUTION

SESSION

LEARNING
CHAMPION
CHALLENGER
DRIFT

DATABASE
LOGGING

DASHBOARD
```

Contoh:

```env
TRADING_MODE=analysis

MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
MT5_PATH=

SYMBOLS=XAUUSD,EURUSD

HTF=M15
MTF=M5
LTF=M1

HTF_WINDOW=200
MTF_WINDOW=200
LTF_WINDOW=200

NETWORK_TYPE=
HIDDEN_SIZE=
DROPOUT=
LEARNING_RATE=
BATCH_SIZE=
EPOCHS=
RANDOM_SEED=

W_HTF=
W_MTF=
W_LTF=
W_STRUCTURE=
W_ORDERFLOW=
W_REGIME=
W_MOMENTUM=
W_NEURAL=

MIN_DIRECTION_SCORE=
MIN_DIRECTION_MARGIN=
MIN_BRAINFLOW_SCORE=
MIN_CONFIDENCE=

MIN_RR=

RISK_PER_TRADE=
MAX_DAILY_RISK=
MAX_DAILY_LOSS=
MAX_CONSECUTIVE_LOSSES=
MAX_OPEN_POSITIONS=
MAX_TOTAL_EXPOSURE=
MAX_CORRELATED_EXPOSURE=

MAX_SPREAD=
MAX_SLIPPAGE=

TRADING_SESSION_START=
TRADING_SESSION_END=
NO_NEW_ENTRY_AFTER=
FORCE_FLAT_TIME=

RETRAIN_ENABLED=true
SHADOW_MODE_ENABLED=true
AUTO_PROMOTION_ENABLED=false

DASHBOARD_ENABLED=true
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=
```

Jangan menyebarkan magic numbers di source code.

Secret `.env` wajib masuk `.gitignore`.

Buat `.env.example`.

Gunakan typed config validation.

---

# 70. TRADING MODES

Wajib:

```text
analysis
paper
live
```

Default development:

```env
TRADING_MODE=analysis
```

Jangan default ke live.

---

# 71. PRE-TRADE OUTPUT

```text
================================================
TRADE OPPORTUNITY
================================================

Symbol:
Broker Symbol:
Timestamp:

HTF:
MTF:
LTF:
Regime:

HTF Strength:      0.xx
MTF Quality:       0.xx
LTF Quality:       0.xx

Structure:          0.xx
Orderflow:          0.xx
Regime Fitness:     0.xx
Momentum:           0.xx

NEURAL
BUY:                0.xx
SELL:               0.xx
HOLD:               0.xx

Brainflow:          0.xx
Confidence:         0.xx

Decision:
BUY / SELL / HOLD

Entry:
SL:
TP:

SL Distance:
TP Distance:
RR:

Risk Quality:       0.xx
Risk %:
Lot:
Estimated Loss at SL:

Risk Firewall:
ALLOWED / REJECTED

Reason:

Champion:
Feature Version:
Scaler Version:

================================================
```

---

# 72. POST-TRADE OUTPUT

```text
================================================
TRADE RESULT
================================================

Trade ID:
Symbol:
Direction:

Planned Entry:
Actual Entry:

SL:
TP:
Exit:

Result:

Gross P/L:
Commission:
Swap:
Net P/L:

Realized R:
MFE:
MAE:
Slippage:
Duration:

Original Brainflow:
Original Confidence:

Champion:
Feature Version:

WHAT WORKED:
...

WHAT FAILED:
...

LEARNING OBSERVATION:
...

================================================
```

---

# 73. DAILY RECAP

```text
DAILY REPORT

Observations:
Opportunities:

BUY:
SELL:
HOLD:

Executed:
Rejected:

Wins:
Losses:
Breakeven:

Win Rate:
Profit Factor:
Expectancy:

Net P/L:
Total R:
Average R:
Max Drawdown:

Average RR:
Average MFE:
Average MAE:

TP:
SL:
Strategy Exit:
Time Exit:

Performance by Symbol:
Performance by Regime:
Performance by Session:
Performance by Direction:

Champion Health:
Drift:
Challenger Status:
```

---

# 74. PROJECT STRUCTURE

Gunakan struktur modular:

```text
mt5_neural_scalper/
│
├── main.py
├── .env.example
├── requirements.txt
├── README.md
│
├── config/
│   ├── settings.py
│   └── validation.py
│
├── layer1_market/
│   ├── mt5_client.py
│   ├── broker_discovery.py
│   ├── symbol_resolver.py
│   ├── market_data.py
│   ├── validator.py
│   ├── features.py
│   ├── structure.py
│   ├── regime.py
│   ├── orderflow.py
│   └── sequences.py
│
├── layer2_brain/
│   ├── network.py
│   ├── encoders.py
│   ├── inference.py
│   ├── brainflow.py
│   ├── decision.py
│   └── opportunity.py
│
├── layer3_execution/
│   ├── trade_planner.py
│   ├── stops.py
│   ├── targets.py
│   ├── risk.py
│   ├── sizing.py
│   ├── executor.py
│   ├── monitor.py
│   ├── reconciliation.py
│   └── recovery.py
│
├── layer4_learning/
│   ├── journal.py
│   ├── observations.py
│   ├── dataset.py
│   ├── labeling.py
│   ├── trainer.py
│   ├── evaluator.py
│   ├── backtest.py
│   ├── walkforward.py
│   ├── shadow.py
│   ├── champion.py
│   ├── challenger.py
│   └── drift.py
│
├── dashboard/
│   ├── api.py
│   ├── websocket.py
│   ├── schemas.py
│   ├── commands.py
│   ├── auth.py
│   └── frontend/
│
├── storage/
│   ├── database/
│   ├── datasets/
│   ├── models/
│   ├── scalers/
│   ├── reports/
│   └── logs/
│
└── tests/
```

Jangan membuat monolithic Python file.

---

# 75. DEVELOPMENT PHASES

Kerjakan bertahap.

### PHASE 0 — DESIGN

- requirement audit;
- dependency audit;
- data contracts;
- feature schema;
- label design;
- leakage audit;
- neural baseline;
- `.env.example`;
- project structure.

### PHASE 1 — MARKET INTELLIGENCE

- MT5;
- broker discovery;
- generic symbols;
- data validation;
- features;
- regime;
- structure;
- orderflow;
- sequences.

### PHASE 2 — LOCAL NEURAL BRAIN

- encoders;
- fusion;
- training baseline;
- inference;
- BUY/SELL/HOLD;
- Brainflow.

### PHASE 3 — RISK & EXECUTION

- Entry;
- deterministic SL;
- deterministic TP;
- RR;
- sizing;
- risk firewall;
- execution;
- monitor;
- reconciliation;
- recovery.

### PHASE 4 — MEMORY & EVOLUTION

- journal;
- observation dataset;
- labels;
- training;
- backtesting;
- walk-forward;
- Champion/Challenger;
- shadow;
- drift.

### PHASE 5 — DASHBOARD

- API;
- WebSocket;
- overview;
- market;
- neural;
- opportunities;
- positions;
- history;
- Trade Replay;
- performance;
- learning;
- risk;
- system health.

### PHASE 6 — INTEGRATION

- analysis mode;
- paper mode;
- long-duration test;
- failure recovery;
- dashboard isolation.

### PHASE 7 — LIVE-READINESS AUDIT

Jangan otomatis mengaktifkan live.

---

# 76. TEST REQUIREMENTS

Test minimal:

```text
broker discovery
symbol normalization
symbol resolution
ambiguous symbol rejection

data quality
incomplete candle exclusion
timeframe alignment

point-in-time features
future leakage
target leakage
scaler leakage

sequence shapes
multi-timeframe synchronization

neural training
deterministic inference
all scores 0–1

BUY/SELL/HOLD
direction margin
Brainflow weights

SL
TP
RR
position sizing

risk veto
spread rejection
slippage rejection
daily loss rejection

duplicate-order prevention

execution failure handling

reconciliation
restart recovery

MFE
MAE

dataset labels
chronological split
purge/embargo
walk-forward

Champion/Challenger
shadow mode
drift

backtest/live feature parity

dashboard unavailable → trading continues
WebSocket reconnect
secret masking
invalid dashboard command
pause/resume
live confirmation
promotion confirmation

dashboard cannot bypass risk
dashboard cannot call order_send directly
dashboard cannot alter weights directly

training worker cannot block critical trading loop
```

---

# 77. ABSOLUTE PROHIBITIONS

Dilarang:

```text
external decision model
pretrained decision model
external trading signal

random BUY/SELL
dummy signals

fake orderflow

future leakage
look-ahead bias
target leakage
scaler leakage

martingale
loss chasing
unsafe averaging

entry without SL

duplicate orders

hardcoded broker suffix
hardcoded broker specification
hidden timeframe assumptions

silent critical exceptions

uncontrolled self-modification
unvalidated Champion replacement

dashboard-controlled direct order execution

backtest/live strategy divergence
```

---

# 78. FINAL FULL-PROJECT AUDIT

Sebelum menyatakan selesai, audit seluruh repository untuk:

```text
external decision dependencies

broker assumptions
symbol hardcoding
timeframe hardcoding
magic numbers

data leakage
look-ahead
scaler leakage
label leakage

incorrect sequence alignment

incorrect neural/scaler pairing
weights/version mismatch

SL/TP errors
RR errors
lot sizing errors

risk bypass

duplicate execution

timezone bugs
session bugs

race conditions
reconnect bugs
restart bugs

unmanaged positions

training blocking live execution

selection bias
overfitting
class imbalance

unsafe Champion promotion
catastrophic forgetting

backtest/live divergence
paper/live divergence

dashboard coupling
dashboard security

config outside .env
secret exposure

missing/error-prone reconciliation
```

Critical issue harus diperbaiki sebelum project dianggap selesai.

---

# 79. FINAL SYSTEM DEFINITION

Sistem akhir harus bekerja sebagai satu closed-loop:

```text
                          MT5
                           │
                           ▼
                LAYER 1 — MARKET
                           │
                           ▼
                LAYER 2 — NEURAL
                           │
                 BUY / SELL / HOLD
                           │
                           ▼
                 LAYER 3 — RISK
                           │
                  ALLOW / REJECT
                           │
                           ▼
                      EXECUTION
                           │
                           ▼
                        RESULT
                           │
                           ▼
                LAYER 4 — MEMORY
                           │
                           ▼
                       TRAINING
                           │
                           ▼
                      CHALLENGER
                           │
                           ▼
              WALK-FORWARD / OOS
                           │
                           ▼
                    SHADOW TEST
                           │
                           ▼
                 VALIDATED BETTER?
                     │           │
                    NO          YES
                     │           │
                  REJECT      PROMOTION
                                 │
                                 ▼
                          NEW CHAMPION
                                 │
                                 └────→ LAYER 2
```

Dashboard mengobservasi seluruh lifecycle tersebut tanpa menjadi sumber keputusan.

---

# 80. IMPLEMENTATION INSTRUCTION

Mulai dari **Phase 0**, bukan langsung menulis seluruh project.

Pertama lakukan:

1. audit requirement ini;
2. identifikasi dependency minimal;
3. tentukan data contract antar-layer;
4. tentukan schema database;
5. tentukan generic symbol strategy;
6. tentukan generic timeframe implementation;
7. tentukan point-in-time feature schema;
8. tentukan labeling strategy;
9. tentukan neural baseline;
10. tentukan normalization;
11. tentukan Brainflow contract;
12. tentukan deterministic SL/TP contract;
13. tentukan risk contract;
14. tentukan Champion/Challenger lifecycle;
15. tentukan dashboard API/event contract;
16. buat `.env.example`;
17. buat project tree;
18. identifikasi seluruh risiko look-ahead/data leakage.

Setelah Phase 0 tervalidasi:

**implementasikan Phase 1 → 2 → 3 → 4 → 5 → 6 → 7 secara berurutan.**

Setelah setiap phase:

- jalankan test;
- laporkan file yang dibuat/diubah;
- laporkan fungsi utama;
- laporkan hasil test;
- audit hardcoding;
- audit leakage;
- audit safety;
- audit error handling;
- audit configuration;
- perbaiki critical failure sebelum melanjutkan.

Jangan meninggalkan:

```text
TODO kritis
dummy trading logic
random signal
fake success
placeholder execution
silent failure
```

Jangan menyatakan system **live-ready** hanya karena aplikasi berhasil berjalan.

Sistem baru dianggap siap ketika:

**data benar → neural inference benar → keputusan dapat direproduksi → SL/TP/RR benar → risk firewall benar → execution benar → reconciliation benar → learning bebas leakage → Challenger tervalidasi → dashboard dapat mengaudit semuanya → failure recovery berhasil.**

Tujuan akhirnya bukan membuat sistem yang selalu entry.

Tujuannya adalah membangun sistem lokal yang terus belajar dari data dan pengalaman sendiri sehingga semakin baik dalam membedakan:

**GOOD BUY**

**GOOD SELL**

**NO EDGE → HOLD**

sementara **deterministic risk firewall tetap menjadi otoritas terakhir atas modal.**