from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from app.collectors.normalizer import RawJob
from app.core.config import settings
from app.utils.job_location import detect_job_location


def job_posting_schema(job: RawJob, post_url: str) -> str:
    """Create Google JobPosting schema with only valid Google-supported values."""

    title = job.post_name or job.title
    description = _clean_description(job)
    job_location = detect_job_location(job)
    schema = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": title,
        "description": description,
        "datePosted": (job.published_at or datetime.utcnow()).date().isoformat(),
        "validThrough": (datetime.utcnow() + timedelta(days=45)).date().isoformat(),
        "employmentType": "FULL_TIME",
        "hiringOrganization": {
            "@type": "Organization",
            "name": job.organization or "Recruiting Organization",
            "sameAs": settings.site_base_url,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "IN",
                "addressRegion": job_location,
            },
        },
        "applicantLocationRequirements": {"@type": "Country", "name": "India"},
        "url": post_url,
    }

    if "remote" in title.lower() or "work from home" in description.lower():
        schema["jobLocationType"] = "TELECOMMUTE"

    salary = _salary_schema(job)
    if salary:
        schema["baseSalary"] = salary

    return json.dumps(schema, ensure_ascii=False)


def _clean_description(job: RawJob) -> str:
    text = f"{job.title}. Organization: {job.organization or 'Recruiting Organization'}. Post: {job.post_name or job.title}. Vacancies: {job.vacancies}."
    return " ".join(text.split())[:500]


def _salary_schema(job: RawJob) -> dict | None:
    details = job.extra.get("details", {}) if isinstance(job.extra, dict) else {}
    raw = " ".join(
        str(value or "")
        for value in [details.get("salary_details") if isinstance(details, dict) else "", job.summary]
    )
    # Only add baseSalary when an actual rupee amount is present in the source details.
    numbers = []
    for match in re.finditer(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]{2,})", raw, flags=re.IGNORECASE):
        try:
            numbers.append(int(match.group(1).replace(",", "")))
        except ValueError:
            pass
    if not numbers:
        return None
    value = {"@type": "QuantitativeValue", "unitText": "MONTH"}
    if len(numbers) >= 2:
        value["minValue"] = min(numbers)
        value["maxValue"] = max(numbers)
    else:
        value["value"] = numbers[0]
    return {"@type": "MonetaryAmount", "currency": "INR", "value": value}


def faq_schema(faqs: list[dict[str, str]]) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in faqs
        ],
    }
    return json.dumps(schema, ensure_ascii=False)


def breadcrumb_schema(title: str, category: str, post_url: str) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": settings.site_name, "item": settings.site_base_url},
            {
                "@type": "ListItem",
                "position": 2,
                "name": category,
                "item": f"{settings.site_base_url}/search/label/{category.replace(' ', '%20')}",
            },
            {"@type": "ListItem", "position": 3, "name": title, "item": post_url},
        ],
    }
    return json.dumps(schema, ensure_ascii=False)
