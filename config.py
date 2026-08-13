"""Application configuration.

All secrets and environment-specific values are read from environment
variables (loaded from a local .env file in development via python-dotenv).
Nothing sensitive is hard-coded here. Required secrets fail fast at startup
so a misconfigured deploy cannot silently fall back to insecure defaults.
"""
import os

from dotenv import load_dotenv

# Load .env as early as possible so config values are available at import time
# (this module is imported before create_app runs). Idempotent.
load_dotenv()


class ConfigError(RuntimeError):
    """Raised when a required configuration value is missing."""


def _require(name):
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Required environment variable {name!r} is not set. "
            f"Copy .env.example to .env and fill it in (see README/setup notes)."
        )
    return value


def _normalize_db_url(url):
    """Normalize a Supabase/Postgres URL for SQLAlchemy + psycopg2.

    - Supabase copy-paste often uses the 'postgres://' scheme, which
      SQLAlchemy no longer accepts; rewrite it to 'postgresql://'.
    - Ensure TLS is requested (Supabase requires SSL).
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


class BaseConfig:
    # --- Core security ---
    SECRET_KEY = _require("SECRET_KEY")

    # --- Database (Supabase / Postgres) ---
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_require("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Supabase's pooler can drop idle connections; recycle + pre-ping
        # keeps the pool healthy.
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # --- URL generation (used by Celery email tasks outside a request) ---
    SERVER_NAME = os.environ.get("SERVER_NAME")  # e.g. "localhost:5050" in dev
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")

    # --- Uploads ---
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))  # 10 MB

    # --- Mail (Gmail SMTP) ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = _require("MAIL_USERNAME")
    MAIL_PASSWORD = _require("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME

    # --- Celery / Redis ---
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # --- Error monitoring / logging ---
    SENTRY_DSN = os.environ.get("SENTRY_DSN")  # unset => Sentry disabled
    SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    SENTRY_ENVIRONMENT = os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "production"
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_DIR = os.environ.get("LOG_DIR", "logs")

    # --- AI document intake (Anthropic) ---
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")  # unset => AI analysis disabled
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

    # --- Auth ---
    # When true, new accounts are confirmed on registration (no confirmation
    # email needed). Defaults off in production; DevelopmentConfig flips it on so
    # local sign-up works without a running Celery worker + mail server.
    AUTO_CONFIRM_EMAIL = os.environ.get("AUTO_CONFIRM_EMAIL", "false").lower() == "true"

    # --- CSRF ---
    WTF_CSRF_TIME_LIMIT = None  # tokens valid for the session lifetime

    # --- Session cookie hardening ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    # No Celery/Redis + mail server locally → confirm accounts on sign-up so
    # you can log in immediately. Override with AUTO_CONFIRM_EMAIL=false to
    # exercise the real confirmation flow.
    AUTO_CONFIRM_EMAIL = os.environ.get("AUTO_CONFIRM_EMAIL", "true").lower() == "true"


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Only send session cookies over HTTPS in production.
    SESSION_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    """Config for the pytest suite. Uses whatever DATABASE_URL the test harness
    sets (SQLite by default) and disables CSRF so functional tests can POST
    without fetching a token. Dedicated CSRF tests re-enable it via a subclass.
    """
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost:5050"
    SESSION_COOKIE_SECURE = False
    # SQLite doesn't use / need the Postgres pool tuning.
    SQLALCHEMY_ENGINE_OPTIONS = {}


class CsrfTestingConfig(TestingConfig):
    """Testing config with CSRF protection left ON, for CSRF-enforcement tests."""
    WTF_CSRF_ENABLED = True


def get_config():
    """Select the config class from FLASK_ENV / APP_ENV."""
    env = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "production").lower()
    if env in ("dev", "development", "local"):
        return DevelopmentConfig
    return ProductionConfig
