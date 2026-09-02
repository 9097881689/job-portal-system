from __future__ import annotations

import logging
from datetime import datetime

import feedparser

from app.collectors.normalizer import RawJob, clean_html, first_present

logger = logging.getLogger(__name__)


def collect_rss(source: dict) -> list[RawJob]:
    """Fetch and normalize jobs from one RSS/Atom source."""

    if not source.get("enabled", True):
        return []

    feed = feedparser.parse(source["url"])
    if feed.bozo:
        logger.warning("RSS parse warning for %s: %s", source["name"], feed.bozo_exception)

    jobs: list[RawJob] = []
    for entry in feed.entries:
        title = first_present(entry.get("title"), default="Job Notification")
        link = entry.get("link") or source["url"]
        source_job_id = entry.get("id") or entry.get("guid") or link
        published = None
        if entry.get("published_parsed"):
            published = datetime(*entry.published_parsed[:6])

        jobs.append(
            RawJob(
                source_name=source["name"],
                source_job_id=str(source_job_id),
                title=title,
                source_url=link,
                apply_url=link,
                organization=source.get("organization", ""),
                post_name=title,
                published_at=published,
                category_hint=source.get("category_hint", "Latest Jobs"),
                summary=clean_html(entry.get("summary") or entry.get("description")),
                extra={"raw_entry": dict(entry)},
            )
        )

    logger.info("Collected %s jobs from RSS source %s", len(jobs), source["name"])
    return jobs
