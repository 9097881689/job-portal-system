from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.collectors.normalizer import clean_html


SECTION_MARKERS = [
    "Important Dates",
    "Application Fee",
    "Age Limit",
    "Vacancy Details",
    "Educational Qualification",
    "Selection Process",
    "Salary",
    "How to Apply",
    "Important Links",
]


def parse_job_detail(html: str, base_url: str) -> dict:
    """Extract structured job facts from Sarkari-style detail pages.

    We use extracted facts as source data, then write a new article in our own
    language. This avoids copying the source article body while keeping details accurate.
    """

    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()

    text = clean_html(soup.get_text("\n", strip=True))
    lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
    joined = "\n".join(lines)

    links = _extract_links(soup, base_url)
    official_link = _best_official_link(links)
    organization = _first_match(joined, [r"^([A-Za-z].*?(?:Board|Commission|Department|Bank|Force|Court|University|Police|Railway).*?)$"])
    post_name = _first_match(joined, [r"(?i)([^\n]*(?:Recruitment|Online Form|Admit Card|Result|Answer Key)[^\n]*)"])
    vacancies = _first_match(joined, [r"(?i)Total (?:Posts|Post|Vacancy|Vacancies)\s*:?\s*([0-9,]+[^\n]*)", r"\(([0-9,]+\s*Posts)\)"])

    important_dates = _section_key_values(joined, "Important Dates", ["Application Fee", "Age Limit"])
    application_fee = _section_text(joined, "Application Fee", ["Age Limit", "Vacancy Details"])
    age_limit = _section_text(joined, "Age Limit", ["Vacancy Details", "Educational Qualification"])
    qualification = _section_text(joined, "Educational Qualification", ["How to Apply", "Selection Process", "Salary", "Important Links"])
    selection = _section_text(joined, "Selection Process", ["Salary", "How to Apply", "Important Links"])
    salary = _section_text(joined, "Salary", ["How to Apply", "Important Links"])
    how_to_apply = _section_steps(joined, "How to Apply", ["Important Links", "Mode of Selection"])

    return {
        "organization": organization,
        "post_name": post_name,
        "vacancies": vacancies,
        "important_dates": important_dates,
        "application_fee": application_fee,
        "age_limit": age_limit,
        "educational_qualification": qualification,
        "selection_process": selection,
        "salary_details": salary,
        "how_to_apply": how_to_apply,
        "important_links": links,
        "official_link": official_link,
        "source_excerpt": _compact(text, 1800),
    }


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    wanted = ["apply", "online", "notification", "official", "download", "admit", "result", "answer key"]
    blocked_domains = {
        "sarkariexam.com",
        "www.sarkariexam.com",
        "sarkariresult.com.cm",
        "www.sarkariresult.com.cm",
        "play.google.com",
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
        "facebook.com",
        "www.facebook.com",
        "instagram.com",
        "www.instagram.com",
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "t.me",
        "telegram.me",
        "whatsapp.com",
        "chat.whatsapp.com",
    }
    blocked_words = [
        "whatsapp",
        "telegram",
        "youtube",
        "instagram",
        "facebook",
        "twitter",
        "x.com",
        "play.google",
        "google play",
        "android app",
        "mobile app",
        "app download",
        "sarkariresulttools",
        "follow now",
        "join",
    ]
    for anchor in soup.select("a[href]"):
        label = clean_html(anchor.get_text(" ", strip=True))
        href = urljoin(base_url, anchor.get("href", ""))
        haystack = f"{label} {href}".lower()
        domain = urlparse(href).netloc.lower()
        if not label or len(label) < 3:
            continue
        if not domain or domain in blocked_domains:
            continue
        if "sarkariresult.com.cm" in haystack or "sarkariexam.com" in haystack:
            continue
        if any(blocked in haystack for blocked in blocked_words):
            continue
        if not any(word in haystack for word in wanted):
            continue
        if any(item["url"] == href for item in links):
            continue
        links.append({"label": label[:80], "url": href})
        if len(links) >= 8:
            break
    return links


def _best_official_link(links: list[dict[str, str]]) -> str:
    priority_words = ["apply", "online", "official", "notification", "download"]
    for word in priority_words:
        for item in links:
            haystack = f"{item['label']} {item['url']}".lower()
            if word in haystack:
                return item["url"]
    return links[0]["url"] if links else ""


def _section_key_values(text: str, start: str, end_markers: list[str]) -> dict[str, str]:
    section = _between(text, start, end_markers)
    result: dict[str, str] = {}
    lines = [line.strip(" :-") for line in section.splitlines() if line.strip()]
    for index, line in enumerate(lines[:-1]):
        if ":" in line:
            key, value = line.split(":", 1)
            result[_clean_key(key)] = value.strip(" :-") or lines[index + 1]
        elif line.endswith(":"):
            result[_clean_key(line)] = lines[index + 1]
        elif any(word in line.lower() for word in ["date", "last", "fee payment", "exam", "admit", "correction"]):
            next_line = lines[index + 1].strip(" :-")
            if next_line and len(next_line) < 80:
                result[_clean_key(line)] = next_line
    return result or {"details": "Official notification ke according dates update hongi."}


def _section_text(text: str, start: str, end_markers: list[str]) -> str:
    section = _between(text, start, end_markers)
    return _compact(section, 900) or "Official notification देखें."


def _section_steps(text: str, start: str, end_markers: list[str]) -> list[str]:
    section = _between(text, start, end_markers)
    lines = [line.strip(" •-*") for line in section.splitlines() if line.strip()]
    steps = [line for line in lines if len(line) > 20][:6]
    if steps:
        return steps
    return [
        "Official website/source link open करें.",
        "Notification, eligibility, fee aur last date carefully check करें.",
        "Apply Online link se form fill करें.",
        "Documents upload करके final submit के बाद print/save कर लें.",
    ]


def _between(text: str, start: str, end_markers: list[str]) -> str:
    start_index = text.lower().find(start.lower())
    if start_index < 0:
        return ""
    content = text[start_index + len(start) :]
    end_positions = [content.lower().find(marker.lower()) for marker in end_markers]
    end_positions = [position for position in end_positions if position > 0]
    if end_positions:
        content = content[: min(end_positions)]
    return content.strip(" :-\n")


def _first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return clean_html(match.group(1))
    return ""


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")[:40] or "date"


def _compact(value: str, limit: int) -> str:
    value = re.sub(r"\n{2,}", "\n", value)
    value = re.sub(r"[ \t]+", " ", value).strip()
    return value[:limit].rstrip()
