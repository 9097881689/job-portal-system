from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
import os


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Central application settings loaded from environment variables."""

    app_env: str = os.getenv("APP_ENV", "production")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/job_portal.db")

    publish_target: Literal["cloudflare", "blogger", "both"] = os.getenv("PUBLISH_TARGET", "cloudflare")  # type: ignore[assignment]
    cloudflare_api_url: str = os.getenv("CLOUDFLARE_API_URL", "https://thedailyjob.pages.dev/api/publish")
    cloudflare_api_token: str = os.getenv("CLOUDFLARE_API_TOKEN", "tdj_auto_post_secret_key_2026")

    blogger_blog_id: str = os.getenv("BLOGGER_BLOG_ID", "")
    blogger_client_secrets_file: Path = ROOT_DIR / os.getenv(
        "BLOGGER_CLIENT_SECRETS_FILE", "config/google_client_secret.json"
    )
    blogger_token_file: Path = ROOT_DIR / os.getenv("BLOGGER_TOKEN_FILE", "config/blogger_token.json")
    publish_mode: Literal["draft", "publish", "schedule"] = os.getenv("PUBLISH_MODE", "draft")  # type: ignore[assignment]
    schedule_after_minutes: int = int(os.getenv("SCHEDULE_AFTER_MINUTES", "0"))

    ai_provider: Literal["openai", "gemini", "deepseek", "openrouter", "template"] = os.getenv("AI_PROVIDER", "template")  # type: ignore[assignment]
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    site_name: str = os.getenv("SITE_NAME", "Sarkari Job Portal")
    site_base_url: str = os.getenv("SITE_BASE_URL", "https://www.example.com").rstrip("/")
    default_featured_image: str = os.getenv("DEFAULT_FEATURED_IMAGE", "")
    google_analytics_id: str = os.getenv("GOOGLE_ANALYTICS_ID", "")
    search_console_verification: str = os.getenv("GOOGLE_SEARCH_CONSOLE_VERIFICATION", "")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    facebook_page_access_token: str = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    facebook_page_id: str = os.getenv("FACEBOOK_PAGE_ID", "")


settings = Settings()
