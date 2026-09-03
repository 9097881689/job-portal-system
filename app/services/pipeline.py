from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.ai.generator import ArticleGenerator
from app.blogger.client import BloggerClient
from app.cloudflare.client import CloudflareClient
from app.collectors.api_collector import collect_api
from app.collectors.predefined_collector import collect_predefined
from app.collectors.rss_collector import collect_rss
from app.collectors.website_collector import collect_website
from app.core.config import ROOT_DIR, settings
from app.models import PublishedPost
from app.services.categorizer import categorize
from app.services.deduplicator import register_or_get_for_update
from app.services.social import share_to_social
from app.utils.images import featured_image_for_labels

logger = logging.getLogger(__name__)


def load_sources(path: Path | None = None) -> dict:
    config_path = path or ROOT_DIR / "config" / "sources.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def collect_all_jobs(sources: dict) -> list:
    jobs = []
    for source in sorted(sources.get("website_sources", []), key=lambda item: item.get("priority", 100)):
        jobs.extend(collect_website(source))
    for source in sources.get("rss_sources", []):
        jobs.extend(collect_rss(source))
    for source in sources.get("api_sources", []):
        jobs.extend(collect_api(source))
    for source in sources.get("predefined_sources", []):
        jobs.extend(collect_predefined(source))
    return jobs


def run_pipeline(db: Session, dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    """Collect new jobs, generate articles, and publish them to Blogger."""

    generator = ArticleGenerator()
    target = getattr(settings, "publish_target", "cloudflare")
    cloudflare = CloudflareClient() if (not dry_run and target in ("cloudflare", "both")) else None
    blogger = BloggerClient() if (not dry_run and target in ("blogger", "both")) else None
    stats = {"collected": 0, "new": 0, "published": 0, "updated": 0, "failed": 0, "duplicates": 0, "queued": 0}

    jobs = collect_all_jobs(load_sources())
    jobs = _dedupe_run(jobs)
    stats["collected"] = len(jobs)
    writes_done = 0

    # First register every collected source item before applying the publish limit.
    # This prevents a source item from being missed just because an earlier run hit --limit.
    work_items = []
    for job in jobs:
        if dry_run:
            work_items.append((job, None, True))
            continue

        record, is_new, needs_write = register_or_get_for_update(db, job)
        if is_new:
            stats["new"] += 1
        if needs_write:
            work_items.append((job, record, is_new))
        else:
            stats["duplicates"] += 1

    for job, record, is_new in work_items:
        if limit and writes_done >= limit:
            stats["queued"] = stats.get("queued", 0) + 1
            continue

        labels = categorize(job)
        featured_image = featured_image_for_labels(labels)

        try:
            article = generator.generate(job, labels, featured_image)
            if dry_run:
                logger.info("Dry run generated article: %s", article.title)
                stats["published"] += 1
                writes_done += 1
                continue

            post_url = ""
            post_id = ""

            if cloudflare:
                existing_cf_id = record.blogger_post_id if (record and record.blogger_post_id) else None
                cf_result = cloudflare.publish_post(
                    title=article.title,
                    html=article.html,
                    labels=labels,
                    slug=article.slug,
                    meta_description=article.meta_description,
                    last_date_raw=getattr(job, "last_date", "") or (job.extra.get("last_date", "") if hasattr(job, "extra") and isinstance(job.extra, dict) else ""),
                    post_id=existing_cf_id,
                )
                post_url = cf_result.get("url") or f"{settings.site_base_url}/{article.slug}"
                post_id = str(cf_result.get("id", ""))
                if cf_result.get("action") == "updated":
                    stats["updated"] += 1
                else:
                    stats["published"] += 1
                writes_done += 1

            if blogger and not cloudflare:
                if record and record.blogger_post_id:
                    result = blogger.update_post(
                        post_id=record.blogger_post_id,
                        title=article.title,
                        html=article.html,
                        labels=labels,
                        meta_description=article.meta_description,
                    )
                    post_id = result.get("id", record.blogger_post_id)
                    post_url = result.get("url") or record.blogger_url or f"{settings.site_base_url}/{article.slug}.html"
                    stats["updated"] += 1
                else:
                    result = blogger.publish_post(
                        title=article.title,
                        html=article.html,
                        labels=labels,
                        slug=article.slug,
                        meta_description=article.meta_description,
                    )
                    post_id = result.get("id")
                    post_url = result.get("url") or f"{settings.site_base_url}/{article.slug}.html"
                    stats["published"] += 1
                    writes_done += 1

            if post_url:
                share_to_social(article.title, post_url)

            record.status = "published"
            record.blogger_post_id = post_id
            record.blogger_url = post_url
            record.content_hash = job.content_hash
            db.add(
                PublishedPost(
                    processed_job_id=record.id,
                    blogger_post_id=post_id,
                    title=article.title,
                    slug=article.slug,
                    labels=",".join(labels),
                    canonical_url=post_url,
                    content_hash=job.content_hash,
                    source_url=job.source_url,
                )
            )
            db.commit()
            writes_done += 1
        except Exception as exc:
            db.rollback()
            if record:
                record.status = "failed"
                record.error_message = str(exc)
                db.add(record)
                db.commit()
            stats["failed"] += 1
            logger.exception("Failed to process job %s", job.title)

    return stats


def _dedupe_run(jobs: list) -> list:
    """Keep the first source hit for a canonical job during one run."""

    unique = {}
    for job in jobs:
        if job.canonical_key not in unique:
            unique[job.canonical_key] = job
    return list(unique.values())
