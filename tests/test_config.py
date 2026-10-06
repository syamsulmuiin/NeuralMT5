import pytest

from config.settings import Settings, TradingMode
from config.validation import validate_settings


def test_default_mode_is_analysis():
    settings = validate_settings(Settings(_env_file=None))
    assert settings.trading_mode is TradingMode.ANALYSIS


def test_brainflow_weights_sum_to_one():
    settings = validate_settings(Settings(_env_file=None))
    assert sum(settings.brainflow_weights) == pytest.approx(1.0)


def test_invalid_brainflow_sum_rejected():
    settings = Settings(_env_file=None, w_neural=0.13)
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_settings(settings)


def test_invalid_timeframe_rejected():
    settings = Settings(_env_file=None, htf="M7")
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        validate_settings(settings)


def test_live_requires_credentials():
    settings = Settings(_env_file=None, trading_mode="live")
    with pytest.raises(ValueError, match="requires explicit MT5"):
        validate_settings(settings)


def test_auto_promotion_is_blocked_in_phase0():
    settings = Settings(_env_file=None, auto_promotion_enabled=True)
    with pytest.raises(ValueError, match="prohibited"):
        validate_settings(settings)
