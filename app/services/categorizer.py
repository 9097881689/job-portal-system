from __future__ import annotations

from pathlib import Path
import re

import yaml

from app.collectors.normalizer import RawJob
from app.core.config import ROOT_DIR


def load_categories(path: Path | None = None) -> dict:
    config_path = path or ROOT_DIR / "config" / "categories.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["categories"]


def categorize(job: RawJob, categories: dict | None = None) -> list[str]:
    """Assign Blogger labels from the job title first.

    Sarkari listing pages often contain mixed sidebar text in summaries. If we
    classify using that whole text, a result can accidentally get "Latest Jobs"
    or a form can land in "Results". Title-first rules keep Blogger labels clean.
    """

    categories = categories or load_categories()
    labels: list[str] = []

    title_text = job.title.lower()

    title_rules: list[tuple[str, list[str]]] = [
        ("Results", ["result", "score card", "marks", "merit list", "cut off", "final list", "reserve list"]),
        ("Admit Card", ["admit card", "hall ticket", "call letter", "exam city", "city slip", "exam date", "interview letter", "pet", "pst", "dv"]),
        ("Answer Key", ["answer key", "response sheet", "objection"]),
        ("Syllabus", ["syllabus", "exam pattern"]),
        ("Latest Jobs", [
            "online form",
            "apply online",
            "recruitment",
            "vacancy",
            "bharti",
            "form",
            "notification",
            "apprentice",
        ]),
    ]

    for label, keywords in title_rules:
        if any(keyword in title_text for keyword in keywords):
            labels.append(label)

    sector_rules: list[tuple[str, list[str]]] = [
        ("Railway Jobs", ["railway", "rrb", "rrc", "metro rail", "dfccil"]),
        ("Bank Jobs", ["bank", "ibps", "sbi", "rbi", "nabard", "idbi", "insurance", "lic hfl"]),
        ("Defence Jobs", [
            "army",
            "navy",
            "air force",
            "defence",
            "defense",
            "bsf",
            "cisf",
            "crpf",
            "itbp",
            "ssb",
            "assam rifles",
            "agniveer",
        ]),
        ("State Government Jobs", [
            "bpsc",
            "upsssc",
            "uppsc",
            "rpsc",
            "hpsc",
            "mppsc",
            "bihar",
            "uttar pradesh",
            "up ",
            "rajasthan",
            "haryana",
            "madhya pradesh",
            "jharkhand",
            "uttarakhand",
            "delhi",
        ]),
        ("Private Jobs", ["private", "company", "fresher", "walk in", "campus"]),
    ]

    for label, keywords in sector_rules:
        if any(_has_keyword(title_text, keyword) for keyword in keywords):
            labels.append(label)

    if not labels:
        labels.append(job.category_hint or "Latest Jobs")

    if "Latest Jobs" in labels or any(label.endswith("Jobs") for label in labels):
        labels.append("Government Jobs")

    return list(dict.fromkeys(labels))


def _has_keyword(text: str, keyword: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
