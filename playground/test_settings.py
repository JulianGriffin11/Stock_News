"""Smoke-test Settings + the Python profile. Does not hit the network.

Run from the repo root:

    uv run python playground/test_settings.py
"""

from app.config.settings import Settings


def run() -> None:
    settings = Settings()
    print("name:", settings.profile.name)
    print("title:", settings.profile.title)
    print("tickers:", settings.tickers)
    print("names:", settings.ticker_names)
    print("window days:", settings.window_days)
    print("window start:", settings.window_start().isoformat())
    print("data dir:", settings.data_dir)
    print("recipient:", settings.profile.recipient)
    print("database_url set:", bool(settings.database_url))
    print("openai_api_key set:", bool(settings.openai_api_key))
    print("resend_api_key set:", bool(settings.resend_api_key))
    print("resend_from set:", bool(settings.resend_from))
    print("week_start:", settings.week_start().isoformat())


if __name__ == "__main__":
    run()
