from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


def round_to_tick(price: float, tick_size: float, *, mode: str = "nearest") -> float:
    if price <= 0 or tick_size <= 0:
        raise ValueError("price and tick_size must be positive")
    p = Decimal(str(price))
    t = Decimal(str(tick_size))
    units = p / t
    rounding = {
        "nearest": ROUND_HALF_UP,
        "down": ROUND_FLOOR,
        "up": ROUND_CEILING,
    }.get(mode)
    if rounding is None:
        raise ValueError("mode must be nearest, down, or up")
    return float(units.to_integral_value(rounding=rounding) * t)
