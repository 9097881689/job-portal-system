from __future__ import annotations

import logging
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import httplib2

from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/blogger"]


class BloggerClient:
    """Small wrapper around Blogger API v3 post publishing."""

    def __init__(self) -> None:
        if not settings.blogger_blog_id:
            raise RuntimeError("BLOGGER_BLOG_ID is required.")
        credentials = self._credentials()
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=45))
        self.service = build("blogger", "v3", http=http, cache_discovery=False)

    def _credentials(self) -> Credentials:
        token_file = settings.blogger_token_file
        if token_file.exists():
            return Credentials.from_authorized_user_file(str(token_file), SCOPES)

        if not settings.blogger_client_secrets_file.exists():
            raise FileNotFoundError(
                f"Missing Google OAuth client file: {settings.blogger_client_secrets_file}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(str(settings.blogger_client_secrets_file), SCOPES)
        credentials = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def publish_post(
        self,
        *,
        title: str,
        html: str,
        labels: list[str],
        slug: str,
        meta_description: str,
    ) -> dict:
        body = {
            "kind": "blogger#post",
            "blog": {"id": settings.blogger_blog_id},
            "title": title,
            "content": html,
            "labels": labels,
            "customMetaData": meta_description,
        }

        is_draft = settings.publish_mode == "draft"
        if settings.publish_mode == "schedule":
            body["published"] = (
                datetime.utcnow() + timedelta(minutes=settings.schedule_after_minutes)
            ).isoformat(timespec="seconds") + "Z"

        logger.info("Sending post to Blogger: %s", title)
        request = self.service.posts().insert(
            blogId=settings.blogger_blog_id,
            body=body,
            isDraft=is_draft,
            fetchBody=False,
            fetchImages=True,
        )
        result = request.execute()

        # Blogger does not accept a slug during insert. This update improves permalinks when supported.
        if result.get("id") and slug:
            try:
                self.service.posts().patch(
                    blogId=settings.blogger_blog_id,
                    postId=result["id"],
                    body={"url": f"{settings.site_base_url}/{slug}.html"},
                ).execute()
            except Exception as exc:  # Blogger may reject URL patching on some blogs.
                logger.info("Slug patch skipped for Blogger post %s: %s", result["id"], exc)

        return result

    def update_post(
        self,
        *,
        post_id: str,
        title: str,
        html: str,
        labels: list[str],
        meta_description: str,
    ) -> dict:
        """Update an existing Blogger post when the source job is changed."""

        body = {
            "title": title,
            "content": html,
            "labels": labels,
            "customMetaData": meta_description,
        }
        logger.info("Updating Blogger post %s: %s", post_id, title)
        return (
            self.service.posts()
            .patch(
                blogId=settings.blogger_blog_id,
                postId=post_id,
                body=body,
                fetchBody=False,
                fetchImages=True,
            )
            .execute()
        )
