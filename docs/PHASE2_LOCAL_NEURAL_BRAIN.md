# Phase 2 — Local Neural Brain

## Scope

Phase 2 implements only the local neural/evidence layer. It does not create absolute Entry,
SL, TP, lot size or send MT5 orders. Those remain Layer 3 responsibilities.

## Architecture

Three independent branches process HTF, MTF and LTF sequences. Each branch uses Conv1D ->
ReLU -> GRU. Their final hidden states are fused by a small dense network. Heads produce:

- BUY / SELL / HOLD probabilities (softmax, sum ~= 1);
- setup quality and direction confidence (sigmoid, 0..1);
- favorable/adverse excursion estimates (non-negative softplus outputs).

There are no pretrained weights and no external decision APIs. `set_deterministic(seed)` seeds
Python, NumPy and PyTorch and enables deterministic algorithms where supported.

## Normalization and schema safety

`StandardScalerArtifact.fit()` accepts training rows only by contract. Validation/test/live
must call `transform()` with the persisted scaler. The artifact stores ordered feature names;
feature order or schema mismatch fails closed. No live fitting exists in the inference module.

## Model/scaler pairing

A model artifact stores network version, scaler version, ordered feature names, random seed and
SHA-256 of weights. Loading verifies the expected feature schema, scaler version and weights
hash before inference.

## Decision contract

The neural classifier is not plain argmax. BUY/SELL must pass all of:

- MIN_DIRECTION_SCORE;
- MIN_DIRECTION_MARGIN;
- MIN_CONFIDENCE;
- MIN_BRAINFLOW_SCORE;
- directional probability must exceed HOLD.

Otherwise the output is HOLD. Brainflow is an eight-input weighted sum and remains in 0..1.
Weights are validated by config to sum to 1.0.

## Training baseline

The baseline multi-task loss combines categorical direction loss, quality/confidence MSE and
Smooth-L1 excursion loss. `train_epoch` rejects empty batches and non-finite loss. Dataset
splitting, labeling, walk-forward and Champion/Challenger promotion remain Layer 4 concerns.

## Safety boundary

A passing neural opportunity is evidence, not permission to trade. Layer 3 must refresh the
market, derive deterministic Entry/SL/TP/RR, size risk and apply the absolute Risk Firewall veto.
