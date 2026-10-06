from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.domain import Direction, NeuralOutput
from contracts.events import EventType, SystemEvent


def test_score_outside_zero_one_is_rejected():
    with pytest.raises(ValidationError):
        NeuralOutput(
            buy_score=1.01, sell_score=0.0, hold_score=0.0,
            setup_quality=0.5, direction_confidence=0.5,
            expected_favorable_excursion=1.0, expected_adverse_excursion=0.5,
        )


def test_probabilities_must_sum_to_one():
    with pytest.raises(ValidationError):
        NeuralOutput(
            buy_score=0.6, sell_score=0.3, hold_score=0.2,
            setup_quality=0.5, direction_confidence=0.5,
            expected_favorable_excursion=1.0, expected_adverse_excursion=0.5,
        )


def test_direction_is_categorical():
    assert [d.value for d in Direction] == ["BUY", "SELL", "HOLD"]


def test_system_event_contract():
    event = SystemEvent(
        event_type=EventType.SYSTEM_WARNING,
        occurred_at_utc=datetime.now(UTC),
        source="test",
        payload={"reason": "example"},
    )
    assert event.event_type is EventType.SYSTEM_WARNING
