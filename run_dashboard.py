from config.settings import Settings
from config.validation import validate_settings
from dashboard.api import create_app


def main() -> None:
    import uvicorn
    settings = validate_settings(Settings())
    if not settings.dashboard_enabled:
        raise SystemExit("Dashboard is disabled in configuration")
    uvicorn.run(create_app(settings), host=settings.dashboard_host, port=settings.dashboard_port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
