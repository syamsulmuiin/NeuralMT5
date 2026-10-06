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


def test_symbols_csv_from_dotenv_is_supported(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SYMBOLS=XAUUSD,EURUSD,GBPUSD\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.symbols == ["XAUUSD", "EURUSD", "GBPUSD"]


def test_utc_timezone_does_not_require_zoneinfo_database(monkeypatch):
    import config.timezones as timezones
    from datetime import timezone

    def _fail_zoneinfo(_name: str):
        raise AssertionError("ZoneInfo must not be consulted for UTC")

    monkeypatch.setattr(timezones, "ZoneInfo", _fail_zoneinfo)
    assert timezones.resolve_timezone("UTC") is timezone.utc
    assert timezones.resolve_timezone("Etc/UTC") is timezone.utc


def test_invalid_timezone_is_rejected():
    settings = Settings(_env_file=None, trading_timezone="Definitely/Not_A_Zone")
    with pytest.raises(ValueError, match="TRADING_TIMEZONE is invalid"):
        validate_settings(settings)


def test_timeframe_roles_must_be_strictly_ordered():
    settings = Settings(_env_file=None, htf="M5", mtf="M15", ltf="M1")
    with pytest.raises(ValueError, match="HTF > MTF > LTF"):
        validate_settings(settings)
