from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (.../eventflow), not CWD — so `uvicorn …` picks up REDIS_URL etc. from `.env` from any directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_PATHS = (
    _REPO_ROOT / ".env.example",
    _REPO_ROOT / ".env",
)


class Settings(BaseSettings):
    # `.env.example` first, then `.env` (later files override — user secrets win).
    model_config = SettingsConfigDict(env_file=_DOTENV_PATHS, env_file_encoding="utf-8", extra="ignore")

    env: Literal["local", "dev", "prod", "test"] = "local"
    log_level: str = "INFO"
    service_name: str = Field(default="eventflow", alias="SERVICE_NAME")
    allow_unauthenticated_local: bool = Field(default=True, alias="ALLOW_UNAUTHENTICATED_LOCAL")

    db_url: Optional[str] = Field(default=None, alias="DB_URL")
    # Optional DB pieces for environments where constructing DB_URL is easier
    # (Cloud Run / GCE / local dev). If DB_URL is set, it always wins.
    db_scheme: str = Field(default="postgresql+psycopg", alias="DB_SCHEME")
    db_host: Optional[str] = Field(default=None, alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: Optional[str] = Field(default=None, alias="DB_NAME")
    db_user: Optional[str] = Field(default=None, alias="DB_USER")
    db_password: Optional[str] = Field(default=None, alias="DB_PASSWORD")
    db_query: Optional[str] = Field(default=None, alias="DB_QUERY")
    # Required in env=dev|prod: backs ShareParseCache for POST /share/url (first global parse → Gemini; then cache hit).
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    supabase_jwks_url: Optional[str] = Field(default=None, alias="SUPABASE_JWKS_URL")
    supabase_jwt_audience: str = Field(default="authenticated", alias="SUPABASE_JWT_AUDIENCE")
    supabase_jwt_issuer: Optional[str] = Field(default=None, alias="SUPABASE_JWT_ISSUER")

    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    google_maps_api_key: Optional[str] = Field(default=None, alias="GOOGLE_MAPS_API_KEY")
    google_calendar_credentials_json: Optional[str] = Field(
        default=None, alias="GOOGLE_CALENDAR_CREDENTIALS_JSON"
    )
    calendar_token_key: Optional[str] = Field(default=None, alias="CALENDAR_TOKEN_KEY")
    google_oauth_redirect_uri: Optional[str] = Field(default=None, alias="GOOGLE_OAUTH_REDIRECT_URI")

    expo_access_token: Optional[str] = Field(default=None, alias="EXPO_ACCESS_TOKEN")
    admin_user_ids_csv: str | None = Field(default=None, alias="ADMIN_USER_IDS")
    # When non-empty: JWT ``email`` claim must match (case-insensitive); ADMIN_USER_IDS / DB allowlist ignored for admin.
    admin_operator_emails_csv: str | None = Field(default=None, alias="ADMIN_OPERATOR_EMAILS")
    # Bearer-equivalent for moderation / verified toggles from tooling or portal backends.
    admin_api_token: Optional[str] = Field(default=None, alias="ADMIN_API_TOKEN")

    # yt-dlp (social link metadata)
    # Optional path to a Netscape cookies.txt file to improve extraction reliability
    # for sites that require login (notably Instagram).
    yt_dlp_cookie_file: Optional[str] = Field(default=None, alias="YTDLP_COOKIE_FILE")

    # Poster storage (durable, for cross-user dedupe + UI)
    poster_storage_dir: str = Field(default="./data/posters", alias="POSTER_STORAGE_DIR")

    # Stripe payments (subscriptions)
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_premium_price_id: Optional[str] = Field(default=None, alias="STRIPE_PREMIUM_PRICE_ID")
    # Public-facing base URL for Stripe redirects (e.g. https://api.example.com or http://35.202.150.38:8000)
    public_base_url: str = Field(default="http://localhost:8000", alias="PUBLIC_BASE_URL")

    # HTTP middleware
    # CSV of origins allowed for CORS. Wildcards supported as the literal value "*"
    # only when env != prod. In prod, leaving this empty disables CORS entirely
    # (browser clients won't be able to reach the API — fine for native-only).
    # Native iOS/Android fetches are not subject to CORS, so the mobile app works
    # regardless of this setting.
    cors_allow_origins: Optional[str] = Field(default=None, alias="CORS_ALLOW_ORIGINS")
    # CSV of hostnames allowed in the Host header (Starlette TrustedHostMiddleware).
    # Only enforced when env=prod. Set to your public hostname(s), e.g.
    # "api.example.com,api.staging.example.com". Use "*" to disable.
    trusted_hosts: Optional[str] = Field(default=None, alias="TRUSTED_HOSTS")

    @property
    def effective_db_url(self) -> Optional[str]:
        """
        Preferred DB URL for SQLAlchemy.

        Order:
        - DB_URL if set
        - Construct from DB_* parts if enough info is provided
        - None (allowed for local/test API boot; workers will still require DB)
        """
        if self.db_url:
            return self.db_url

        if not self.db_host or not self.db_name:
            return None

        userinfo = ""
        if self.db_user:
            if self.db_password is not None:
                userinfo = f"{self.db_user}:{self.db_password}@"
            else:
                userinfo = f"{self.db_user}@"

        query = f"?{self.db_query.lstrip('?')}" if self.db_query else ""
        return f"{self.db_scheme}://{userinfo}{self.db_host}:{self.db_port}/{self.db_name}{query}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

