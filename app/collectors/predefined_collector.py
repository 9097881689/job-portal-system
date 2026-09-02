from __future__ import annotations

from app.collectors.normalizer import RawJob


def collect_predefined(source: dict) -> list[RawJob]:
    """Load manually configured jobs; useful for official sources without feeds."""

    if not source.get("enabled", True):
        return []

    return [
        RawJob(
            source_name="predefined",
            source_job_id=source["id"],
            title=source["title"],
            source_url=source.get("source_url", source.get("apply_url", "")),
            apply_url=source.get("apply_url", source.get("source_url", "")),
            organization=source.get("organization", ""),
            post_name=source.get("post_name", source["title"]),
            vacancies=source.get("vacancies", "Not specified"),
            category_hint=source.get("category_hint", "Latest Jobs"),
            summary=source.get("summary", ""),
            extra=source,
        )
    ]
