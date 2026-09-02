from __future__ import annotations

import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def share_to_social(title: str, url: str) -> None:
    """Share published posts to optional social channels."""

    if settings.telegram_bot_token and settings.telegram_chat_id:
        endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        requests.post(endpoint, json={"chat_id": settings.telegram_chat_id, "text": f"{title}\n{url}"}, timeout=15)
        logger.info("Shared post to Telegram")

    if settings.facebook_page_access_token and settings.facebook_page_id:
        endpoint = f"https://graph.facebook.com/{settings.facebook_page_id}/feed"
        requests.post(
            endpoint,
            data={"message": title, "link": url, "access_token": settings.facebook_page_access_token},
            timeout=15,
        )
        logger.info("Shared post to Facebook page")
