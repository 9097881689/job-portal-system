from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.normalizer import RawJob, first_present

logger = logging.getLogger(__name__)


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def _get_json(url: str) -> Any:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def collect_api(source: dict) -> list[RawJob]:
    """Fetch jobs from a JSON API source.

    The source config defines which JSON fields contain IDs, titles, URLs, and dates.
    """

    if not source.get("enabled", True):
        return []

    payload = _get_json(source["url"])
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        logger.warning("API source %s did not return a list-like payload", source["name"])
        return []

    jobs: list[RawJob] = []
    for item in items:
        source_job_id = str(item.get(source.get("id_field", "id")) or item.get("url") or item)
        title = first_present(str(item.get(source.get("title_field", "title"), "")), default="Job Notification")
        url = str(item.get(source.get("url_field", "url"), source["url"]))
        date_value = item.get(source.get("date_field", "published_at"))
        published = None
        if isinstance(date_value, str):
            try:
                published = datetime.fromisoformat(date_value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                published = None

        jobs.append(
            RawJob(
                source_name=source["name"],
                source_job_id=source_job_id,
                title=title,
                source_url=url,
                apply_url=url,
                organization=str(item.get("organization", "")),
                post_name=str(item.get("post_name", title)),
                vacancies=str(item.get("vacancies", "Not specified")),
                published_at=published,
                category_hint=source.get("category_hint", "Latest Jobs"),
                summary=str(item.get("summary", "")),
                extra=item,
            )
        )

    logger.info("Collected %s jobs from API source %s", len(jobs), source["name"])
    return jobs
