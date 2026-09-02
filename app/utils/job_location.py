from __future__ import annotations

import re
from typing import Any

from app.collectors.normalizer import RawJob


STATE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Andhra Pradesh", ("andhra pradesh", "ap psc", "appsc")),
    ("Arunachal Pradesh", ("arunachal pradesh",)),
    ("Assam", ("assam", "apsc")),
    ("Bihar", ("bihar", "bpsc", "bpssc", "btsc", "bcece", "bceceb", "bseb", "csbc", "patna high court")),
    ("Chhattisgarh", ("chhattisgarh", "cgpsc", "cg vyapam")),
    ("Delhi", ("delhi", "dsssb")),
    ("Goa", ("goa",)),
    ("Gujarat", ("gujarat", "gpsc", "gsssb")),
    ("Haryana", ("haryana", "hpsc", "hssc", "htet")),
    ("Himachal Pradesh", ("himachal pradesh", "hppsc", "hp police")),
    ("Jharkhand", ("jharkhand", "jpsc", "jssc", "jceceb")),
    ("Karnataka", ("karnataka", "kpsc")),
    ("Kerala", ("kerala", "kerala psc")),
    ("Madhya Pradesh", ("madhya pradesh", "mppsc", "mpesb", "mp police")),
    ("Maharashtra", ("maharashtra", "mpsc", "mumbai", "nagpur")),
    ("Manipur", ("manipur",)),
    ("Meghalaya", ("meghalaya",)),
    ("Mizoram", ("mizoram",)),
    ("Nagaland", ("nagaland",)),
    ("Odisha", ("odisha", "ossc", "opsc")),
    ("Punjab", ("punjab", "ppsc", "pseb")),
    ("Rajasthan", ("rajasthan", "rpsc", "rssb")),
    ("Sikkim", ("sikkim",)),
    ("Tamil Nadu", ("tamil nadu", "tnpsc")),
    ("Telangana", ("telangana", "tspsc")),
    ("Tripura", ("tripura",)),
    ("Uttar Pradesh", ("uttar pradesh", "upsssc", "uppsc", "up police", "upessc", "up board", "jeecup", "abvmu")),
    ("Uttarakhand", ("uttarakhand", "ukpsc")),
    ("West Bengal", ("west bengal", "wbpsc", "wbbse")),
    ("Jammu and Kashmir", ("jammu", "kashmir", "jkpsc", "jkssb")),
]

CENTRAL_PATTERNS = (
    "all india",
    "central government",
    "ssc",
    "upsc",
    "rrb",
    "railway",
    "ibps",
    "rbi",
    "sbi",
    "bank of baroda",
    "indian army",
    "indian navy",
    "indian air force",
    "air force",
    "bsf",
    "cisf",
    "crpf",
    "itbp",
    "ssb",
    "drdo",
    "isro",
    "nta",
    "cbse",
    "kvs",
    "nvs",
    "emrs",
    "aiims",
    "ncert",
    "aibe",
    "lic hfl",
)


def detect_job_location(job: RawJob) -> str:
    """Return a human-readable job location for articles and JobPosting schema."""

    details = job.extra.get("details", {}) if isinstance(job.extra, dict) else {}
    title_text = _normalize(" ".join(str(value or "") for value in [job.title, job.organization, job.post_name]))
    title_location = _detect_from_normalized_text(title_text)
    if title_location:
        return title_location

    text = " ".join(
        str(value or "")
        for value in [
            job.title,
            job.organization,
            job.post_name,
            job.category_hint,
            job.summary,
            _flatten_details(details),
        ]
    )
    return _detect_from_normalized_text(_normalize(text)) or "All India"


def detect_job_location_from_text(*values: str) -> str:
    if values:
        title_location = _detect_from_normalized_text(_normalize(values[0] or ""))
        if title_location:
            return title_location
    text = _normalize(" ".join(value or "" for value in values))
    return _detect_from_normalized_text(text) or "All India"


def _detect_from_normalized_text(text: str) -> str:
    for state, patterns in STATE_PATTERNS:
        if any(_contains_term(text, pattern) for pattern in patterns):
            return state
    if any(_contains_term(text, pattern) for pattern in CENTRAL_PATTERNS):
        return "All India"
    return ""


def _flatten_details(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_details(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_details(item) for item in value)
    return str(value or "")


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None
