from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProcessedJob(Base):
    """Jobs seen by the collector. The unique fingerprint prevents duplicates."""

    __tablename__ = "processed_jobs"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_processed_jobs_fingerprint"),
        UniqueConstraint("canonical_key", name="uq_processed_jobs_canonical_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(160), index=True)
    source_job_id: Mapped[str] = mapped_column(String(255), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    canonical_key: Mapped[str] = mapped_column(String(64), index=True, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text)
    source_priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(40), default="collected", index=True)
    blogger_post_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    blogger_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishedPost(Base):
    """SEO and Blogger metadata for successfully generated/published posts."""

    __tablename__ = "published_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    processed_job_id: Mapped[int] = mapped_column(Integer, index=True)
    blogger_post_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    labels: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
