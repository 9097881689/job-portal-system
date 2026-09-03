from __future__ import annotations

import logging
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudflareClient:
    """Publishes jobs directly to Cloudflare Pages & D1 with clean SEO URLs."""

    def __init__(self) -> None:
        self.api_url = getattr(settings, "cloudflare_api_url", "https://thedailyjob.pages.dev/api/publish")
        self.api_token = getattr(settings, "cloudflare_api_token", "tdj_auto_post_secret_key_2026")

    def publish_post(
        self,
        *,
        title: str,
        html: str,
        labels: list[str],
        slug: str,
        meta_description: str = "",
        last_date_raw: str = "",
        post_id: str | None = None,
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "TheDailyJob-AutoPoster/1.0",
        }
        payload = {
            "id": int(post_id) if post_id and str(post_id).isdigit() else None,
            "title": title,
            "slug": slug,
            "content": html,
            "categories": labels,
            "last_date_raw": last_date_raw,
            "meta_description": meta_description,
        }

        try:
            resp = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Published to Cloudflare: %s -> %s", title, data.get("url"))
            return data
        except Exception as exc:
            logger.exception("Failed to publish to Cloudflare: %s", exc)
            raise
