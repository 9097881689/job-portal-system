from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any
import re

from bs4 import BeautifulSoup


@dataclass
class RawJob:
    """Normalized job data collected from RSS, APIs, or predefined sources."""

    source_name: str
    source_job_id: str
    title: str
    source_url: str
    apply_url: str = ""
    organization: str = ""
    post_name: str = ""
    vacancies: str = "Not specified"
    published_at: datetime | None = None
    category_hint: str = "Latest Jobs"
    summary: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        stable = f"{self.source_name}|{self.source_job_id}|{self.title}|{self.source_url}".lower()
        return sha256(stable.encode("utf-8")).hexdigest()

    @property
    def canonical_key(self) -> str:
        """Stable key for the same update across multiple source websites."""

        title = self.title.lower()
        title = re.sub(r"\b(start|apply here|link active|out|released|updated|new|latest|notification)\b", "", title)
        title = re.sub(r"\b(19|20)\d{2}\b", "", title)
        title = re.sub(r"\b\d{1,6}\s*(post|posts|vacancy|vacancies)\b", "", title)
        title = re.sub(r"\bcen\s*\d+\/\d+\b", "", title)
        title = re.sub(r"[^a-z0-9]+", " ", title)
        title = re.sub(r"\s+", " ", title).strip()
        return sha256(title.encode("utf-8")).hexdigest()

    @property
    def content_hash(self) -> str:
        """Hash changes when title, source URL, summary, or important extracted details change."""

        version = self.extra.get("article_version", "") if isinstance(self.extra, dict) else ""
        details = self.extra.get("details", {}) if isinstance(self.extra, dict) else {}
        stable_detail_keys = [
            "organization",
            "post_name",
            "vacancies",
            "important_dates",
            "application_fee",
            "age_limit",
            "educational_qualification",
            "selection_process",
            "salary_details",
            "important_links",
            "official_link",
        ]
        stable_details = {key: details.get(key) for key in stable_detail_keys if isinstance(details, dict) and details.get(key)}
        stable = f"{version}|{self.title}|{self.source_url}|{self.apply_url}|{self.vacancies}|{stable_details}".lower()
        return sha256(stable.encode("utf-8")).hexdigest()


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    if "<" not in value and ">" not in value:
        return " ".join(value.split())
    return " ".join(BeautifulSoup(value, "html.parser").get_text(" ").split())


def first_present(*values: str | None, default: str = "") -> str:
    for value in values:
        if value:
            cleaned = clean_html(value)
            if cleaned:
                return cleaned
    return default
