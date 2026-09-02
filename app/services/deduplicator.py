from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collectors.normalizer import RawJob
from app.models import ProcessedJob


def register_or_get_for_update(db: Session, job: RawJob) -> tuple[ProcessedJob, bool, bool]:
    """Return a job record plus flags: is_new, needs_publish_or_update.

    Same recruitment seen on both watched sites maps to one canonical key, so it
    will not create a repeated Blogger post. If the source details change later,
    the existing Blogger post is updated instead.
    """

    existing = db.scalar(select(ProcessedJob).where(ProcessedJob.source_url == job.source_url))
    if not existing:
        existing = db.scalar(select(ProcessedJob).where(ProcessedJob.fingerprint == job.fingerprint))
    if not existing:
        existing = db.scalar(select(ProcessedJob).where(ProcessedJob.canonical_key == job.canonical_key))
    if not existing:
        existing = _find_similar_existing(db, job)
    if existing:
        source_priority = int(job.extra.get("source_priority", existing.source_priority))
        if source_priority <= existing.source_priority:
            existing.source_name = job.source_name
            existing.source_job_id = job.source_job_id
            existing.fingerprint = job.fingerprint
            existing.title = job.title[:255]
            existing.source_url = job.source_url
            existing.source_priority = source_priority
        existing.canonical_key = job.canonical_key

        needs_update = existing.content_hash != job.content_hash or not existing.blogger_post_id or existing.status == "failed"
        if needs_update:
            existing.content_hash = job.content_hash
            existing.status = "update_pending" if existing.blogger_post_id else "collected"
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            exact_existing = db.scalar(select(ProcessedJob).where(ProcessedJob.fingerprint == job.fingerprint))
            if not exact_existing:
                exact_existing = db.scalar(select(ProcessedJob).where(ProcessedJob.source_url == job.source_url))
            if exact_existing:
                return exact_existing, False, exact_existing.content_hash != job.content_hash or exact_existing.status == "failed"
            raise
        db.refresh(existing)
        return existing, False, needs_update

    record = ProcessedJob(
        source_name=job.source_name,
        source_job_id=job.source_job_id,
        fingerprint=job.fingerprint,
        canonical_key=job.canonical_key,
        content_hash=job.content_hash,
        title=job.title[:255],
        source_url=job.source_url,
        source_priority=int(job.extra.get("source_priority", 100)),
        status="collected",
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
        return record, True, True
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ProcessedJob).where(ProcessedJob.canonical_key == job.canonical_key))
        if existing:
            return existing, False, False
        raise


def _find_similar_existing(db: Session, job: RawJob) -> ProcessedJob | None:
    """Match older records created before the stronger canonical key existed."""

    new_signature = _title_signature(job.title)
    if not new_signature:
        return None
    for record in db.scalars(select(ProcessedJob).order_by(ProcessedJob.id.desc()).limit(100)):
        if _title_signature(record.title) == new_signature:
            return record
    return None


def _title_signature(title: str) -> str:
    text = title.lower()
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)
    text = re.sub(r"\b\d{1,6}\s*(post|posts|vacancy|vacancies)\b", " ", text)
    text = re.sub(r"\bcen\s*\.?\s*no\s*\.?\s*\d+\/\d+\b", " ", text)
    text = re.sub(r"\bcen\s*\d+\/\d+\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop_words = {
        "apply",
        "here",
        "online",
        "form",
        "notification",
        "recruitment",
        "result",
        "out",
        "released",
        "latest",
        "new",
        "railway",
        "railways",
        "cen",
        "no",
    }
    tokens = [token for token in text.split() if token not in stop_words and not token.isdigit() and len(token) > 1]
    return " ".join(tokens[:6])
