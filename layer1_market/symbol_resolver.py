from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from contracts.domain import SymbolResolution
from layer1_market.models import BrokerSymbolSpec

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_KNOWN_ALIASES: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("XAUUSD", "GOLD"),
    "XAGUSD": ("XAGUSD", "SILVER"),
}
_DEFAULT_EXCLUDE_TOKENS = ("REPLAY", "REPALY", "PLAYBACK")


def normalize_symbol(value: str) -> str:
    return _NON_ALNUM.sub("", value.upper().strip())


def _canonical_currencies(canonical: str) -> tuple[str, str] | None:
    n = normalize_symbol(canonical)
    if len(n) == 6 and n.isalpha():
        return n[:3], n[3:]
    if n == "XAUUSD":
        return "XAU", "USD"
    if n == "XAGUSD":
        return "XAG", "USD"
    return None


@dataclass(frozen=True)
class _Candidate:
    spec: BrokerSymbolSpec
    score: float
    reasons: tuple[str, ...]
    rejected_reason: str | None = None

    @property
    def eligible(self) -> bool:
        return self.rejected_reason is None


def _rejected_reason(spec: BrokerSymbolSpec, exclude_tokens: Sequence[str]) -> str | None:
    # MT5 custom symbols are terminal-local synthetic instruments and must never be
    # selected as live/training broker instruments.
    if spec.custom:
        return "custom MT5 symbol"
    # 0=disabled, 3=close-only. Neither can accept a new trading position.
    if spec.trade_mode in (0, 3):
        return f"trade_mode={spec.trade_mode} cannot open new positions"

    searchable = normalize_symbol(f"{spec.name} {spec.description} {spec.path}")
    for raw in exclude_tokens:
        token = normalize_symbol(raw)
        if token and token in searchable:
            return f"excluded token: {raw.upper()}"
    return None


def _score(canonical: str, spec: BrokerSymbolSpec, *, exclude_tokens: Sequence[str]) -> _Candidate:
    rejected = _rejected_reason(spec, exclude_tokens)
    if rejected:
        return _Candidate(spec=spec, score=0.0, reasons=(), rejected_reason=rejected)

    canonical_n = normalize_symbol(canonical)
    name_n = normalize_symbol(spec.name)
    aliases = tuple(normalize_symbol(v) for v in _KNOWN_ALIASES.get(canonical_n, (canonical_n,)))
    score = 0.0
    reasons: list[str] = []

    if name_n == canonical_n:
        score += 0.92
        reasons.append("exact normalized symbol")
    elif any(name_n == alias for alias in aliases):
        score += 0.58
        reasons.append("known semantic alias")
    elif any(name_n.startswith(alias) or name_n.endswith(alias) for alias in aliases):
        # A canonical token at either edge of the broker symbol is a strong identity
        # signal (e.g. XAUUSD.vx, XAUUSDm, mXAUUSD). It must be able to clear the
        # default 0.90 threshold when broker metadata is partially populated.
        score += 0.68
        reasons.append("canonical name with broker affix")
    elif any(alias in name_n for alias in aliases):
        score += 0.22
        reasons.append("canonical token present")

    currencies = _canonical_currencies(canonical_n)
    if currencies:
        base, profit = currencies
        if spec.currency_base == base:
            score += 0.16
            reasons.append("base currency match")
        if spec.currency_profit == profit:
            score += 0.16
            reasons.append("profit currency match")

    text = normalize_symbol(f"{spec.description} {spec.path}")
    if canonical_n in text or any(alias in text for alias in aliases):
        score += 0.04
        reasons.append("description/path match")

    if spec.trade_mode in (1, 2, 4):
        score += 0.02
        reasons.append("trade-enabled metadata")

    return _Candidate(spec=spec, score=min(score, 1.0), reasons=tuple(reasons))


def inspect_symbol_candidates(
    canonical: str,
    symbols: Sequence[BrokerSymbolSpec],
    *,
    exclude_tokens: Sequence[str] = _DEFAULT_EXCLUDE_TOKENS,
) -> list[dict[str, object]]:
    """Return deterministic resolver diagnostics without changing selection behavior."""
    candidates = [_score(canonical, s, exclude_tokens=exclude_tokens) for s in symbols]
    candidates.sort(key=lambda c: (c.eligible, c.score, normalize_symbol(c.spec.name)), reverse=True)
    return [
        {
            "broker_symbol": c.spec.name,
            "eligible": c.eligible,
            "score": round(c.score, 6),
            "rejected_reason": c.rejected_reason,
            "trade_mode": c.spec.trade_mode,
            "custom": c.spec.custom,
            "visible": c.spec.visible,
            "reasons": list(c.reasons),
        }
        for c in candidates
    ]


def resolve_symbol(
    canonical: str,
    symbols: Sequence[BrokerSymbolSpec],
    *,
    min_confidence: float = 0.90,
    override: str | None = None,
    ambiguity_margin: float = 0.03,
    exclude_tokens: Sequence[str] = _DEFAULT_EXCLUDE_TOKENS,
) -> SymbolResolution:
    canonical = normalize_symbol(canonical)
    if not canonical:
        raise ValueError("canonical symbol cannot be empty")

    if override:
        target = normalize_symbol(override)
        matches = [s for s in symbols if normalize_symbol(s.name) == target]
        if len(matches) == 1:
            rejected = _rejected_reason(matches[0], exclude_tokens)
            if rejected:
                return SymbolResolution(
                    canonical_symbol=canonical,
                    broker_symbol=None,
                    resolution_confidence=0.0,
                    reason=f"manual override rejected: {rejected}",
                )
            return SymbolResolution(
                canonical_symbol=canonical,
                broker_symbol=matches[0].name,
                resolution_confidence=1.0,
                reason="manual override matched eligible broker symbol",
            )
        return SymbolResolution(
            canonical_symbol=canonical,
            broker_symbol=None,
            resolution_confidence=0.0,
            reason="manual override not found or ambiguous",
            ambiguous=len(matches) > 1,
        )

    all_ranked = [_score(canonical, s, exclude_tokens=exclude_tokens) for s in symbols]
    ranked = sorted((c for c in all_ranked if c.eligible), key=lambda c: c.score, reverse=True)
    if not ranked or ranked[0].score < min_confidence:
        best = ranked[0] if ranked else None
        if best is None:
            rejected = [c for c in all_ranked if c.rejected_reason]
            if rejected:
                details = ", ".join(f"{c.spec.name} ({c.rejected_reason})" for c in rejected[:3])
                reason = f"no eligible candidate; rejected: {details}"
            else:
                reason = "no candidate"
        else:
            reason = f"best candidate below threshold: {best.spec.name}={best.score:.3f}"
        return SymbolResolution(
            canonical_symbol=canonical,
            broker_symbol=None,
            resolution_confidence=best.score if best else 0.0,
            reason=reason,
        )

    best = ranked[0]
    if len(ranked) > 1 and ranked[1].score >= min_confidence and best.score - ranked[1].score <= ambiguity_margin:
        return SymbolResolution(
            canonical_symbol=canonical,
            broker_symbol=None,
            resolution_confidence=best.score,
            reason=f"ambiguous candidates: {best.spec.name}={best.score:.3f}, {ranked[1].spec.name}={ranked[1].score:.3f}",
            ambiguous=True,
        )

    return SymbolResolution(
        canonical_symbol=canonical,
        broker_symbol=best.spec.name,
        resolution_confidence=best.score,
        reason="; ".join(best.reasons),
    )


def resolve_many(
    canonicals: Sequence[str],
    symbols: Sequence[BrokerSymbolSpec],
    *,
    min_confidence: float,
    overrides: Mapping[str, str | None] | None = None,
    exclude_tokens: Sequence[str] = _DEFAULT_EXCLUDE_TOKENS,
) -> dict[str, SymbolResolution]:
    overrides = overrides or {}
    return {
        normalize_symbol(c): resolve_symbol(
            c,
            symbols,
            min_confidence=min_confidence,
            override=overrides.get(normalize_symbol(c)),
            exclude_tokens=exclude_tokens,
        )
        for c in canonicals
    }
