from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.detail_parser import parse_job_detail
from app.collectors.normalizer import RawJob, clean_html

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

NOISE_WORDS = {
    "home",
    "menu",
    "privacy policy",
    "contact us",
    "about us",
    "disclaimer",
    "join whatsapp",
    "image resizer",
    "age calculator",
    "cv maker",
    "sarkari result",
    "sarkari result™",
    "skip to content",
    "latest job",
    "admit card",
    "result",
    "answer keys",
    "answer key",
    "syllabus",
    "admission",
    "more",
    "view more",
    "view all",
    "view all »",
}

ALLOWED_UPDATE_WORDS = [
    "online form",
    "form ",
    "recruitment",
    "admit card",
    "exam city",
    "exam date",
    "result",
    "answer key",
    "objection",
    "syllabus",
    "score card",
    "marks",
    "merit list",
    "reserve list",
    "provisional list",
    "vacancy",
    "posts",
    "notification",
    "pet",
    "pst",
    "cbt",
    "dv",
]


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def _get_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.text


def collect_website(source: dict) -> list[RawJob]:
    """Scrape public listing pages and return newest links first.

    This collector only uses title/link/nearby text as signals. The article generator
    writes original Hindi content instead of copying source-page paragraphs.
    """

    if not source.get("enabled", True):
        return []

    jobs: list[RawJob] = []
    seen_urls: set[str] = set()
    source_name = source["name"]
    base_url = source["base_url"]
    allowed_domain = urlparse(base_url).netloc.replace("www.", "")
    max_items = int(source.get("max_items", 30))
    max_items_per_listing = int(source.get("max_items_per_listing", max_items))

    for direct_url in source.get("direct_urls", []):
        href = urljoin(base_url, direct_url)
        parsed = urlparse(href)
        domain = parsed.netloc.replace("www.", "")
        if domain and domain != allowed_domain:
            continue
        if href in seen_urls:
            continue
        job = _job_from_url(
            href=href,
            title="",
            source=source,
            source_name=source_name,
            listing_url="direct",
        )
        jobs.append(job)
        seen_urls.add(href)

    for listing_url in source.get("listing_urls", []):
        listing_count = 0
        try:
            html = _get_html(listing_url)
        except Exception as exc:
            logger.warning("Could not fetch listing page %s: %s", listing_url, exc)
            continue
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            title = clean_html(link.get_text(" ", strip=True))
            href = urljoin(listing_url, link.get("href", ""))
            parsed = urlparse(href)
            domain = parsed.netloc.replace("www.", "")

            if not title or len(title) < 12:
                continue
            if domain and domain != allowed_domain:
                continue
            if href in seen_urls:
                continue
            if title.lower() in NOISE_WORDS:
                continue
            if not _is_update_title(title):
                continue
            if _looks_like_tool_or_page(title, href):
                continue
            if "/category/" in href or href.rstrip("/").endswith(
                ("/latest-jobs", "/admit-card", "/result", "/answer-key", "/syllabus", "/admission")
            ):
                continue

            jobs.append(
                _job_from_url(
                    href=href,
                    title=title,
                    source=source,
                    source_name=source_name,
                    listing_url=listing_url,
                    summary=_nearby_text(link),
                )
            )
            seen_urls.add(href)
            listing_count += 1

            if len(jobs) >= max_items or listing_count >= max_items_per_listing:
                break
        if len(jobs) >= max_items:
            break

    logger.info("Collected %s jobs from website source %s", len(jobs), source_name)
    return jobs


def _job_from_url(
    *,
    href: str,
    title: str,
    source: dict,
    source_name: str,
    listing_url: str,
    summary: str = "",
) -> RawJob:
    details = _details_for(href) if source.get("fetch_details", True) else {}
    detail_title = _clean_source_branding(details.get("post_name", ""))
    listing_title = _clean_source_branding(title)
    page_title = detail_title if _usable_title(detail_title) else listing_title or _title_from_url(href)
    official_link = details.get("official_link", "")
    return RawJob(
        source_name=source_name,
        source_job_id=href,
        title=page_title,
        source_url=href,
        apply_url=official_link,
        organization=details.get("organization", ""),
        post_name=details.get("post_name") or page_title,
        vacancies=details.get("vacancies") or "Not specified",
        category_hint=source.get("category_hint", "Latest Jobs"),
        summary=details.get("source_excerpt") or summary,
        extra={
            "listing_url": listing_url,
            "source_priority": source.get("priority", 100),
            "article_version": "openrouter-master-ai-v13",
            "details": details,
        },
    )


def _looks_like_tool_or_page(title: str, href: str) -> bool:
    value = f"{title} {href}".lower()
    blocked = ["tool", "privacy", "contact", "about", "disclaimer", "whatsapp", "telegram", "youtube"]
    allowed = [
        "online form",
        "recruitment",
        "admit card",
        "result",
        "answer key",
        "syllabus",
        "vacancy",
        "bharti",
        "exam date",
        "notification",
    ]
    return any(word in value for word in blocked) and not any(word in value for word in allowed)


def _is_update_title(title: str) -> bool:
    value = f" {title.lower()} "
    return any(word in value for word in ALLOWED_UPDATE_WORDS)


def _nearby_text(link) -> str:
    parent = link.find_parent(["li", "p", "tr", "div"])
    return clean_html(parent.get_text(" ", strip=True) if parent else link.get_text(" ", strip=True))


def _details_for(url: str) -> dict:
    try:
        return parse_job_detail(_get_html(url), url)
    except Exception as exc:
        logger.warning("Could not extract detail page %s: %s", url, exc)
        return {}


def _title_from_url(url: str) -> str:
    slug = urlparse(url).path.strip("/").split("/")[-1]
    return " ".join(part.upper() if part in {"rrb", "ssc", "upsc"} else part.title() for part in slug.split("-"))


def _clean_source_branding(value: str) -> str:
    text = clean_html(value)
    for word in ["Sarkari Result™", "Sarkari Result", "SarkariExam", "Sarkari Exam"]:
        text = text.replace(word, "")
    return " ".join(text.split()).strip(" -|:")


def _usable_title(value: str) -> bool:
    lower = value.lower().strip()
    if len(lower) < 12:
        return False
    return lower not in {"result", "latest jobs", "admit card", "answer key", "syllabus"}
