# Phase 4 Audit

- External decision model: none.
- Pretrained model: none.
- Training outcome can directly execute orders: no.
- Auto Champion replacement: blocked.
- Explicit promotion confirmation: required.
- Historical feature mutation: observation insert is immutable; labels attach once only.
- Target leakage control: labels stored separately from feature payload and created post-horizon.
- Split leakage control: chronological ordering + purge/embargo + horizon overlap removal.
- Same-bar backtest optimism: ambiguous SL/TP ordering resolves to HOLD.
- Dataset reproducibility: deterministic content hash.
- Rollback history: previous Champion becomes RETIRED and promotion is audited.
