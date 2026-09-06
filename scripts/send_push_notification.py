#!/usr/bin/env python3
"""
Send Web Push Notifications to all subscribers using OneSignal REST API.
"""

import argparse
import json
import logging
import os
import sys
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("push_notification")


def send_notification(
    *,
    title: str,
    message: str,
    url: str,
    app_id: str | None = None,
    api_key: str | None = None,
) -> dict:
    app_id = app_id or os.getenv("ONESIGNAL_APP_ID", "")
    api_key = api_key or os.getenv("ONESIGNAL_REST_API_KEY", "")

    if not app_id or not api_key:
        logger.warning("OneSignal APP_ID or REST_API_KEY not configured. Skipping push notification.")
        return {"skipped": True, "reason": "Missing credentials"}

    endpoint = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {api_key}",
    }

    payload = {
        "app_id": app_id,
        "included_segments": ["All"],
        "headings": {"en": title},
        "contents": {"en": message},
        "url": url,
        "chrome_web_badge": "https://thedailyjob.in/favicon.ico",
        "chrome_web_icon": "https://thedailyjob.in/favicon.ico",
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        res_data = response.json()
        if response.status_code == 200:
            recipients = res_data.get("recipients", 0)
            logger.info("Successfully sent push notification to %d subscribers! (ID: %s)", recipients, res_data.get("id"))
        else:
            logger.error("Failed to send push notification (%d): %s", response.status_code, res_data)
        return res_data
    except Exception as exc:
        logger.error("Exception sending push notification: %s", exc)
        return {"error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description="Send Push Notification to TheDailyJob subscribers")
    parser.add_argument("--title", required=True, help="Notification Title")
    parser.add_argument("--message", required=True, help="Notification Message / Short description")
    parser.add_argument("--url", required=True, help="Click target URL")
    args = parser.parse_args()

    send_notification(title=args.title, message=args.message, url=args.url)


if __name__ == "__main__":
    main()
