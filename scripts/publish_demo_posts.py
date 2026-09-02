from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import time

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings


SCOPES = ["https://www.googleapis.com/auth/blogger"]


DEMO_POSTS = [
    {
        "title": "Demo Latest Job 2026 - Online Form Started",
        "labels": ["Latest Jobs", "Government Jobs"],
        "body": "यह demo latest job post है. Isse homepage ke Top Online Form / Latest Jobs section test hoga.",
    },
    {
        "title": "Demo Admit Card 2026 - Download Link Active",
        "labels": ["Admit Card"],
        "body": "यह demo admit card post है. Isse homepage ke Admit Card section test hoga.",
    },
    {
        "title": "Demo Result 2026 - Merit List Released",
        "labels": ["Results"],
        "body": "यह demo result post है. Isse homepage ke Result section test hoga.",
    },
    {
        "title": "Demo Answer Key 2026 - Objection Link Open",
        "labels": ["Answer Key"],
        "body": "यह demo answer key post है. Isse homepage ke Answer Keys section test hoga.",
    },
    {
        "title": "Demo Syllabus 2026 - Exam Pattern Available",
        "labels": ["Syllabus"],
        "body": "यह demo syllabus post है. Isse homepage ke Syllabus section test hoga.",
    },
    {
        "title": "Demo Admission Form 2026 - Apply Online",
        "labels": ["Admission", "Latest Jobs"],
        "body": "यह demo admission form post है. Isse homepage ke Admission Form section test hoga.",
    },
]


def main() -> None:
    credentials = Credentials.from_authorized_user_file(str(settings.blogger_token_file), SCOPES)
    service = build("blogger", "v3", credentials=credentials, cache_discovery=False)
    created_at = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    existing_titles = _existing_titles(service)

    for post in DEMO_POSTS:
        if post["title"] in existing_titles:
            print("SKIP", post["title"])
            continue
        html = f"""
        <article>
          <h2>{post["title"]}</h2>
          <p><strong>{post["body"]}</strong></p>
          <table>
            <tbody>
              <tr><th>Post Type</th><td>{", ".join(post["labels"])}</td></tr>
              <tr><th>Status</th><td>Demo post for Blogger layout testing</td></tr>
              <tr><th>Created</th><td>{created_at}</td></tr>
            </tbody>
          </table>
          <p>Note: यह सिर्फ demo/testing post है. Real job update नहीं है.</p>
        </article>
        """
        result = _insert_with_retry(service, post, html)
        print(result.get("title"), result.get("url"))
        time.sleep(4)


def _existing_titles(service) -> set[str]:
    response = (
        service.posts()
        .list(blogId=settings.blogger_blog_id, maxResults=50, status=["LIVE", "DRAFT"], fetchBodies=False)
        .execute()
    )
    return {item.get("title", "") for item in response.get("items", [])}


def _insert_with_retry(service, post: dict, html: str) -> dict:
    for attempt in range(3):
        try:
            return (
                service.posts()
                .insert(
                    blogId=settings.blogger_blog_id,
                    body={
                        "kind": "blogger#post",
                        "blog": {"id": settings.blogger_blog_id},
                        "title": post["title"],
                        "content": html,
                        "labels": post["labels"],
                    },
                    isDraft=False,
                    fetchBody=False,
                    fetchImages=False,
                )
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status != 429 or attempt == 2:
                raise
            time.sleep(20 * (attempt + 1))
    raise RuntimeError("Could not publish demo post")


if __name__ == "__main__":
    main()
