#!/usr/bin/env python3
"""
Google Indexing API Client for TheDailyJob.in
Publishes instant crawl notifications to Google Search for JobPosting URLs.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("instant_indexing")

ROOT_DIR = Path(__file__).resolve().parents[1]
SERVICE_ACCOUNT_FILE = ROOT_DIR / "config" / "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/indexing"]
INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"


def get_credentials():
    if not SERVICE_ACCOUNT_FILE.exists():
        logger.error(
            "Service account file not found at: %s\n"
            "Please follow the instructions to download your Service Account JSON key "
            "from Google Cloud Console and save it to config/service_account.json.",
            SERVICE_ACCOUNT_FILE
        )
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
        )
        return creds
    except Exception as exc:
        logger.error("Failed to load service account credentials: %s", exc)
        return None


def submit_url(url: str, creds, action: str = "URL_UPDATED") -> dict:
    """Submit a single URL to Google Indexing API."""
    if not creds.valid:
        creds.refresh(Request())

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {creds.token}",
    }
    payload = {
        "url": url,
        "type": action,
    }

    resp = requests.post(INDEXING_ENDPOINT, json=payload, headers=headers, timeout=20)
    data = resp.json()
    if resp.status_code == 200:
        logger.info("Successfully submitted to Google: %s (Time: %s)", url, data.get("urlNotificationMetadata", {}).get("latestUpdate", {}).get("notifyTime"))
    else:
        logger.error("Google Indexing API error for %s (%d): %s", url, resp.status_code, data)
    return data


def submit_urls_batch(urls: list[str], creds, action: str = "URL_UPDATED"):
    """Submit a list of URLs to Google Indexing API."""
    success = 0
    failed = 0
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            res = submit_url(url, creds, action)
            if "error" not in res:
                success += 1
            else:
                failed += 1
        except Exception as exc:
            logger.error("Error submitting %s: %s", url, exc)
            failed += 1
    logger.info("Indexing batch completed. Success: %d, Failed: %d", success, failed)


def main():
    parser = argparse.ArgumentParser(description="Send instant indexing request to Google")
    parser.add_argument("--url", help="Single URL to index", default="")
    parser.add_argument("--file", help="File with list of URLs (one per line)", default="")
    parser.add_argument("--action", choices=["URL_UPDATED", "URL_DELETED"], default="URL_UPDATED")
    args = parser.parse_args()

    creds = get_credentials()
    if not creds:
        sys.exit(1)

    if args.url:
        submit_url(args.url, creds, args.action)
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            logger.error("File not found: %s", path)
            sys.exit(1)
        urls = path.read_text().splitlines()
        submit_urls_batch(urls, creds, args.action)
    else:
        # Default: Submit homepage and latest post
        test_url = "https://thedailyjob.in/ibps-rrb-15th-recruitment-2026-hindi"
        logger.info("No URL specified. Submitting test URL: %s", test_url)
        submit_url(test_url, creds, args.action)


if __name__ == "__main__":
    main()
