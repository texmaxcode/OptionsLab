"""Env-based configuration. API key and DB URL from environment; never commit keys."""

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

# Massive.com API key (required for sync). Load from env only.
MASSIVE_API_KEY_ENV = "MASSIVE_API_KEY"

# E*TRADE OAuth (consumer key/secret from developer.etrade.com; tokens from OAuth flow).
ETrade_CONSUMER_KEY_ENV = "ETrade_CONSUMER_KEY"
ETrade_CONSUMER_SECRET_ENV = "ETrade_CONSUMER_SECRET"
ETrade_ACCESS_TOKEN_ENV = "ETrade_ACCESS_TOKEN"
ETrade_ACCESS_SECRET_ENV = "ETrade_ACCESS_SECRET"
ETrade_SANDBOX_ENV = "ETrade_SANDBOX"

# Alpaca Trading API (paper trading uses separate key pair and base URL).
ALPACA_API_KEY_ENV = "APCA_API_KEY_ID"
ALPACA_API_SECRET_ENV = "APCA_API_SECRET_KEY"
ALPACA_BASE_URL_ENV = "APCA_API_BASE_URL"

# Economic data API keys (env-only, never stored in DB)
FRED_API_KEY_ENV = "FRED_API_KEY"
BLS_API_KEY_ENV = "BLS_API_KEY"
BEA_API_KEY_ENV = "BEA_API_KEY"
TRADINGECONOMICS_CLIENT_ENV = "TRADINGECONOMICS_CLIENT"
TRADINGECONOMICS_KEY_ENV = "TRADINGECONOMICS_KEY"


def get_massive_api_key() -> str | None:
    """Return Massive API key from environment. Never hardcode in repo."""
    return os.environ.get(MASSIVE_API_KEY_ENV)


def get_fred_api_key() -> str | None:
    """Return FRED API key from environment."""
    return os.environ.get(FRED_API_KEY_ENV)


def get_bls_api_key() -> str | None:
    """Return BLS API key from environment."""
    return os.environ.get(BLS_API_KEY_ENV)


def get_bea_api_key() -> str | None:
    """Return BEA API key from environment."""
    return os.environ.get(BEA_API_KEY_ENV)


def get_etrade_consumer_key() -> str | None:
    return os.environ.get(ETrade_CONSUMER_KEY_ENV)


def get_etrade_consumer_secret() -> str | None:
    return os.environ.get(ETrade_CONSUMER_SECRET_ENV)


def get_etrade_access_token() -> str | None:
    return os.environ.get(ETrade_ACCESS_TOKEN_ENV)


def get_etrade_access_secret() -> str | None:
    return os.environ.get(ETrade_ACCESS_SECRET_ENV)


def get_etrade_sandbox() -> bool:
    """Use E*TRADE sandbox (default True for safety). Set to false for production."""
    return os.environ.get(ETrade_SANDBOX_ENV, "true").lower() in ("true", "1", "yes")


def get_etrade_credentials(
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
    sandbox: bool | None = None,
) -> tuple[str, str, str, str, bool]:
    """Resolve E*TRADE credentials from args or env. Returns (key, secret, token, token_secret, sandbox)."""
    key = consumer_key or get_etrade_consumer_key()
    secret = consumer_secret or get_etrade_consumer_secret()
    token = access_token or get_etrade_access_token()
    token_secret = access_secret or get_etrade_access_secret()
    dev = sandbox if sandbox is not None else get_etrade_sandbox()
    if not all((key, secret, token, token_secret)):
        raise ValueError(
            "E*TRADE credentials required. Set ETrade_CONSUMER_KEY, ETrade_CONSUMER_SECRET, "
            "ETrade_ACCESS_TOKEN, ETrade_ACCESS_SECRET (or pass to this function)."
        )
    return key, secret, token, token_secret, dev


def get_alpaca_api_key() -> str | None:
    return os.environ.get(ALPACA_API_KEY_ENV)


def get_alpaca_api_secret() -> str | None:
    return os.environ.get(ALPACA_API_SECRET_ENV)


def get_alpaca_base_url() -> str:
    return os.environ.get(ALPACA_BASE_URL_ENV, "https://paper-api.alpaca.markets")


def get_alpaca_credentials(
    api_key: str | None = None,
    api_secret: str | None = None,
) -> tuple[str, str, str]:
    """Resolve Alpaca credentials from args or env. Returns (api_key, api_secret, base_url)."""
    key = api_key or get_alpaca_api_key()
    secret = api_secret or get_alpaca_api_secret()
    base_url = get_alpaca_base_url().rstrip("/")
    if not all((key, secret)):
        raise ValueError(
            "Alpaca paper trading credentials required. Set APCA_API_KEY_ID and "
            "APCA_API_SECRET_KEY (or save Alpaca keys in Settings)."
        )
    return key, secret, base_url


def get_database_url() -> str:
    """Database URL: SQLite by default. Use TRADING_DATABASE_URL or TRADING_DATABASE_SECRET_ARN (AWS)."""
    explicit = os.environ.get("TRADING_DATABASE_URL")
    if explicit:
        return explicit
    secret_arn = os.environ.get("TRADING_DATABASE_SECRET_ARN")
    if secret_arn:
        return _database_url_from_secret(secret_arn)
    return "sqlite:///" + str(Path(__file__).resolve().parents[1] / "trading.db")


_db_url_cache: str | None = None


def _database_url_from_secret(secret_arn: str) -> str:
    """Build PostgreSQL URL from RDS secret (username, password) + optional host/port/dbname or env. Cached per process."""
    global _db_url_cache
    if _db_url_cache is not None:
        return _db_url_cache
    try:
        import boto3
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=secret_arn)
        data = json.loads(resp["SecretString"])
        user = data.get("username", "postgres")
        password = quote_plus(data.get("password", ""))
        host = data.get("host") or data.get("hostname") or os.environ.get("TRADING_DB_HOST", "localhost")
        port = data.get("port") or int(os.environ.get("TRADING_DB_PORT", "5432"))
        dbname = data.get("dbname") or data.get("database") or os.environ.get("TRADING_DB_NAME", "trading")
        _db_url_cache = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        return _db_url_cache
    except Exception:
        raise ValueError(
            "TRADING_DATABASE_SECRET_ARN set but could not read secret. "
            "Ensure Lambda has secretsmanager:GetSecretValue and the secret has username, password; "
            "set TRADING_DB_HOST, TRADING_DB_PORT, TRADING_DB_NAME if not in secret."
        ) from None


def get_sync_default_symbol() -> str:
    """Default underlying symbol for sync (e.g. AAPL)."""
    return os.environ.get("TRADING_DEFAULT_SYMBOL", "AAPL")


def get_sync_date_from() -> str:
    """Default from-date for sync (YYYY-MM-DD)."""
    return os.environ.get("TRADING_SYNC_FROM", "2024-01-01")


def get_sync_date_to() -> str:
    """Default to-date for sync (YYYY-MM-DD)."""
    return os.environ.get("TRADING_SYNC_TO", "2024-12-31")


# ---------------------------------------------------------------------------
# Application environment
# ---------------------------------------------------------------------------

def get_app_env() -> str:
    """Return the current deployment stage: 'dev', 'staging', or 'production'.

    Set APP_ENV in the Lambda environment (done automatically by ApiStack CDK).
    Defaults to 'dev' for local development.
    """
    return os.environ.get("APP_ENV", "dev")


def is_production() -> bool:
    return get_app_env() == "production"


def get_app_version() -> str:
    """Return app version from APP_VERSION env var (set by CI/CD) or 'local'."""
    return os.environ.get("APP_VERSION", "local")


def get_allowed_origins() -> list[str]:
    """Return the CORS allowed origins list.

    In Lambda, ALLOWED_ORIGINS is set by the CDK ApiStack (comma-separated).
    Defaults to ['*'] for local development.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]
