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


def _score(canonical: str, spec: BrokerSymbolSpec) -> _Candidate:
    canonical_n = normalize_symbol(canonical)
    name_n = normalize_symbol(spec.name)
    aliases = tuple(normalize_symbol(v) for v in _KNOWN_ALIASES.get(canonical_n, (canonical_n,)))
    score = 0.0
    reasons: list[str] = []

    if name_n == canonical_n:
        score += 0.62
        reasons.append("exact normalized symbol")
    elif any(name_n == alias for alias in aliases):
        score += 0.58
        reasons.append("known semantic alias")
    elif any(name_n.startswith(alias) or name_n.endswith(alias) for alias in aliases):
        score += 0.56
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

    if spec.trade_mode > 0:
        score += 0.02
        reasons.append("trade-enabled metadata")

    return _Candidate(spec=spec, score=min(score, 1.0), reasons=tuple(reasons))


def resolve_symbol(
    canonical: str,
    symbols: Sequence[BrokerSymbolSpec],
    *,
    min_confidence: float = 0.90,
    override: str | None = None,
    ambiguity_margin: float = 0.03,
) -> SymbolResolution:
    canonical = normalize_symbol(canonical)
    if not canonical:
        raise ValueError("canonical symbol cannot be empty")

    if override:
        target = normalize_symbol(override)
        matches = [s for s in symbols if normalize_symbol(s.name) == target]
        if len(matches) == 1:
            return SymbolResolution(
                canonical_symbol=canonical,
                broker_symbol=matches[0].name,
                resolution_confidence=1.0,
                reason="manual override matched broker symbol",
            )
        return SymbolResolution(
            canonical_symbol=canonical,
            broker_symbol=None,
            resolution_confidence=0.0,
            reason="manual override not found or ambiguous",
            ambiguous=len(matches) > 1,
        )

    ranked = sorted((_score(canonical, s) for s in symbols), key=lambda c: c.score, reverse=True)
    if not ranked or ranked[0].score < min_confidence:
        best = ranked[0] if ranked else None
        reason = "no candidate" if best is None else f"best candidate below threshold: {best.spec.name}={best.score:.3f}"
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
) -> dict[str, SymbolResolution]:
    overrides = overrides or {}
    return {
        normalize_symbol(c): resolve_symbol(
            c,
            symbols,
            min_confidence=min_confidence,
            override=overrides.get(normalize_symbol(c)),
        )
        for c in canonicals
    }
