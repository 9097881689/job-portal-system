from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.blogger.client import BloggerClient
from app.collectors.website_collector import _job_from_url
from app.core.config import settings
from app.db.session import Base, SessionLocal, engine
from app.models import ProcessedJob, PublishedPost
from app.services.categorizer import categorize
from app.services.pipeline import _dedupe_run, collect_all_jobs, load_sources
from app.utils.title_image import title_image_data_uri


HOST = "0.0.0.0"
PORT = 8765


MASTER_PROMPT = """Act as an expert Hindi-English SEO content writer for an Indian Sarkari Job website named TheDailyJob.

Create a fully unique, human-written, SEO-optimized job post in natural Hindi + useful English mixed language. Do not write Roman Hinglish. Use proper Hindi in Devanagari with useful English job keywords.

Rules:
1. Do not copy the source article.
2. Do not mention or link competitor/source website.
3. Do not include Google Play Store, WhatsApp, Telegram, X/Twitter or random external links.
4. Only include official recruitment links and TheDailyJob internal category links.
5. If official links are missing, write "Available Soon" or "Update Soon". Do not create fake links.
6. Return ONLY valid JSON, no markdown.
7. Article should be Blogger-ready HTML.
8. Add feature image metadata.

Return JSON keys:
seo_title, focus_keyword, meta_description, suggested_permalink, labels, featured_image_prompt, featured_image_alt, featured_image_title, featured_image_caption, html

HTML structure:
Introduction, Recruitment Overview table, Notification Details, Important Dates table, Vacancy Details, Eligibility Criteria, Age Limit table, Application Fee table, Selection Process bullets, Salary / Pay Scale, Required Documents, How to Apply Online, Important Links, FAQs, Conclusion.
"""


def main() -> None:
    Base.metadata.create_all(bind=engine)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"TheDailyJob mobile backend running at http://{HOST}:{PORT}")
    server.serve_forever()


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json({"ok": True, "blog_id": settings.blogger_blog_id, "site": settings.site_base_url})
            return
        if parsed.path == "/api/jobs":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", ["90"])[0])
            self._send_json({"jobs": list_jobs(limit=limit)})
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        data = self._read_json()
        if parsed.path == "/api/prompt":
            self._send_json({"prompt": build_prompt(data.get("source_url", ""))})
            return
        if parsed.path == "/api/publish":
            self._send_json(publish_manual(data))
            return
        self._send_json({"error": "Not found"}, status=404)

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0") or "0")
        if not size:
            return {}
        raw = self.rfile.read(size).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def list_jobs(limit: int = 90) -> list[dict]:
    jobs = _dedupe_run(collect_all_jobs(load_sources()))[:limit]
    result: list[dict] = []
    with SessionLocal() as db:
        for job in jobs:
            rec = _find_record(db, job)
            status = "new"
            blogger_post_id = ""
            blogger_url = ""
            if rec and rec.blogger_post_id:
                blogger_post_id = rec.blogger_post_id
                blogger_url = rec.blogger_url or ""
                status = "pending_update" if rec.content_hash != job.content_hash or rec.status in {"failed", "update_pending"} else "published"
            elif rec:
                status = "new"
            result.append(
                {
                    "title": job.title,
                    "source_url": job.source_url,
                    "organization": job.organization,
                    "vacancies": job.vacancies,
                    "labels": categorize(job),
                    "status": status,
                    "blogger_post_id": blogger_post_id,
                    "blogger_url": blogger_url,
                }
            )
    return result


def build_prompt(source_url: str) -> str:
    job = _job_for_url(source_url)
    details = job.extra.get("details", {}) if isinstance(job.extra, dict) else {}
    facts = {
        "title": job.title,
        "source_url_for_reference_only": job.source_url,
        "organization": job.organization,
        "post_name": job.post_name,
        "vacancies": job.vacancies,
        "labels": categorize(job),
        "summary": job.summary,
        "details": details,
    }
    return MASTER_PROMPT + "\n\nRecruitment Details JSON:\n" + json.dumps(facts, ensure_ascii=False, indent=2)


def publish_manual(data: dict) -> dict:
    source_url = data.get("source_url", "")
    article_text = data.get("article_json", "")
    article = json.loads(article_text) if isinstance(article_text, str) else article_text
    job = _job_for_url(source_url)
    labels = article.get("labels") or categorize(job)
    if isinstance(labels, str):
        labels = [item.strip() for item in labels.split(",") if item.strip()]

    title = _clean_text(article.get("seo_title") or article.get("title") or job.title)[:250]
    meta = _clean_text(article.get("meta_description") or f"{job.title} की पूरी जानकारी देखें।")[:155]
    slug = _clean_text(article.get("suggested_permalink") or "")
    html_body = article.get("html") or ""
    html_body = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html_body, flags=re.I | re.S)
    html = _wrap_html(
        title=title,
        meta=meta,
        body=html_body,
        labels=labels,
        image_alt=article.get("featured_image_alt") or title,
        image_title=article.get("featured_image_title") or title,
        image_caption=article.get("featured_image_caption") or "TheDailyJob update image",
    )

    blogger = BloggerClient()
    with SessionLocal() as db:
        rec = _find_record(db, job)
        if rec and rec.blogger_post_id:
            api_result = blogger.update_post(
                post_id=rec.blogger_post_id,
                title=title,
                html=html,
                labels=labels,
                meta_description=meta,
            )
            post_id = api_result.get("id", rec.blogger_post_id)
            url = api_result.get("url") or rec.blogger_url
        else:
            api_result = blogger.publish_post(
                title=title,
                html=html,
                labels=labels,
                slug=slug,
                meta_description=meta,
            )
            post_id = api_result.get("id")
            url = api_result.get("url")
            rec = ProcessedJob(
                source_name=job.source_name,
                source_job_id=job.source_job_id,
                fingerprint=job.fingerprint,
                canonical_key=job.canonical_key,
                content_hash=job.content_hash,
                title=job.title[:255],
                source_url=job.source_url,
                source_priority=int(job.extra.get("source_priority", 100)),
                status="published",
            )

        rec.title = job.title[:255]
        rec.source_url = job.source_url
        rec.fingerprint = job.fingerprint
        rec.canonical_key = job.canonical_key
        rec.content_hash = job.content_hash
        rec.status = "published"
        rec.blogger_post_id = post_id
        rec.blogger_url = url
        db.add(rec)
        db.flush()
        db.add(
            PublishedPost(
                processed_job_id=rec.id,
                blogger_post_id=post_id,
                title=title,
                slug=slug,
                labels=",".join(labels),
                canonical_url=url,
                content_hash=job.content_hash,
                source_url=job.source_url,
            )
        )
        db.commit()

    return {"ok": True, "title": title, "url": url, "post_id": post_id}


def _find_record(db, job):
    return (
        db.scalar(select(ProcessedJob).where(ProcessedJob.source_url == job.source_url))
        or db.scalar(select(ProcessedJob).where(ProcessedJob.fingerprint == job.fingerprint))
        or db.scalar(select(ProcessedJob).where(ProcessedJob.canonical_key == job.canonical_key))
    )


def _job_for_url(source_url: str):
    source = {
        "name": "SarkariResult CM",
        "base_url": "https://sarkariresult.com.cm/",
        "fetch_details": True,
        "category_hint": "Latest Jobs",
        "priority": 1,
    }
    return _job_from_url(href=source_url, title="", source=source, source_name=source["name"], listing_url="manual")


def _wrap_html(title: str, meta: str, body: str, labels: list[str], image_alt: str, image_title: str, image_caption: str) -> str:
    image = title_image_data_uri(title, labels)
    return f"""<article class="job-post se-job-post"><style>.se-job-post{{font-family:Roboto,Arial,Helvetica,sans-serif;color:#1f2937;line-height:1.65;font-size:15px}}.se-job-post h2{{background:#b91c1c;color:#fff;font-size:18px;margin:18px 0 8px;padding:8px 10px;border-radius:4px}}.se-job-post h3{{font-size:16px;margin:14px 0 6px;color:#b91c1c}}.se-job-post table{{width:100%;border-collapse:collapse;margin:10px 0;background:#fff}}.se-job-post th,.se-job-post td{{border:1px solid #d1d5db;padding:9px;text-align:left;vertical-align:top}}.se-job-post th{{background:#f3f4f6}}.se-job-post ul,.se-job-post ol{{padding-left:22px}}.se-job-post .generated-title-image{{margin:0 0 12px}}.se-job-post .generated-title-image img{{display:block;width:100%;height:auto;border:1px solid #e5e7eb;border-radius:6px}}.se-job-post .job-alert{{background:#fff7ed;border:1px solid #fed7aa;padding:10px;border-radius:6px;margin:10px 0}}.se-job-post a{{color:#0b57d0;font-weight:600}}@media(max-width:600px){{.se-job-post th,.se-job-post td{{display:block;width:auto}}.se-job-post h2{{font-size:16px}}}}</style><figure class="generated-title-image"><img alt="{_escape(image_alt)}" title="{_escape(image_title)}" src="{image}" loading="lazy" width="1200" height="630"/><figcaption>{_escape(image_caption)}</figcaption></figure><p class="job-alert"><strong>{_escape(meta)}</strong></p>{body}</article>"""


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _escape(value: object) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    main()
